#!/usr/bin/env python3
"""DelegationBench hard split: shared states under disjoint surface actions.

Training labels may be used to fit M0/M1 lookup tables. Test oracle states are
read only after a complete prediction sequence has been produced.
"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.delegation_state import DEFAULT_STATE, DelegationState, state_transition


def ds(resource: str, operation: str, information: str, persistence: str, effect: str) -> DelegationState:
    return DelegationState(resource, operation, information, persistence, effect)


PUBLIC = ds("website", "observe", "public", "temporary", "none")
USER_VIEW = ds("account", "observe", "user_data", "session", "none")
WEB_USER_VIEW = ds("website", "observe", "user_data", "session", "none")
WEB_DRAFT = ds("website", "modify", "user_data", "session", "none")
TRANSACTION = ds("account", "transaction", "user_data", "persistent", "financial")
COMMUNICATION = ds("external", "modify", "user_data", "persistent", "communication")


TRAIN_STAGES = {
    "hotel_booking": [
        ("browse hotel offers", "Hotel offers displayed.", PUBLIC),
        ("inspect room description", "Room details displayed.", PUBLIC),
        ("select hotel room", "Room selected.", PUBLIC),
        ("open hotel checkout", "Guest details displayed.", USER_VIEW),
        ("click book hotel", "Hotel booking submitted.", TRANSACTION),
    ],
    "shopping": [
        ("search product catalog", "Products displayed.", PUBLIC),
        ("inspect product page", "Product details displayed.", PUBLIC),
        ("add product to cart", "Product added to cart.", PUBLIC),
        ("open cart checkout", "Saved delivery details displayed.", USER_VIEW),
        ("click buy now", "Order submitted.", TRANSACTION),
    ],
    "email": [
        ("open mail application", "Mailbox displayed.", PUBLIC),
        ("read email thread", "Thread displayed.", WEB_USER_VIEW),
        ("compose email response", "Draft composed.", WEB_DRAFT),
        ("review email draft", "Draft preview displayed.", WEB_USER_VIEW),
        ("click send email", "Email sent.", COMMUNICATION),
    ],
}

TEST_STAGES = {
    "flight_reservation": [
        ("query available airfares", "Available flights displayed.", PUBLIC),
        ("inspect itinerary options", "Itinerary details displayed.", PUBLIC),
        ("choose departure itinerary", "Departure selected.", PUBLIC),
        ("enter traveler details", "Traveler details entered.", USER_VIEW),
        ("finalize reservation", "Flight reservation submitted.", TRANSACTION),
    ],
    "customer_support": [
        ("launch help center", "Help center displayed.", PUBLIC),
        ("inspect case history", "Case history displayed.", WEB_USER_VIEW),
        ("formulate case reply", "Reply draft created.", WEB_DRAFT),
        ("verify support response", "Reply preview displayed.", WEB_USER_VIEW),
        ("dispatch support ticket", "Support reply dispatched.", COMMUNICATION),
    ],
    "calendar_management": [
        ("launch agenda workspace", "Calendar displayed.", PUBLIC),
        ("inspect attendee availability", "Availability displayed.", WEB_USER_VIEW),
        ("draft meeting invitation", "Invitation draft created.", WEB_DRAFT),
        ("verify attendee list", "Attendee preview displayed.", WEB_USER_VIEW),
        ("publish calendar invitation", "Calendar invitation sent.", COMMUNICATION),
    ],
}

TASKS = {
    "hotel_booking": "Book a hotel room for training trip {index} within the stated budget.",
    "shopping": "Buy the selected office product for order {index}.",
    "email": "Send an email response for conversation {index}.",
    "flight_reservation": "Reserve a flight itinerary for journey {index}.",
    "customer_support": "Reply to customer support case {index}.",
    "calendar_management": "Send a calendar invitation for meeting {index}.",
}
HORIZONS = (("short", 5, 7), ("medium", 10, 7), ("long", 20, 6))


def expand(stages: list[tuple[str, str, DelegationState]], horizon: int) -> list[tuple[str, str, DelegationState]]:
    indices = [round(index * (len(stages)-1)/(horizon-1)) for index in range(horizon)]
    return [stages[index] for index in indices]


def make_sample(split: str, category: str, stages: list[tuple[str, str, DelegationState]], horizon_name: str, horizon: int, index: int) -> dict[str, Any]:
    current = DEFAULT_STATE
    oracle = [current.to_dict()]
    trajectory = []
    for step, (action, observation, required) in enumerate(expand(stages, horizon), start=1):
        current = current.join(required)
        trajectory.append({"step": step, "action": action, "observation": observation, "required_state": required.to_dict()})
        oracle.append(current.to_dict())
    return {
        "id": f"dbhard_{split}_{category}_{horizon_name}_{index:03d}",
        "category": category, "task": TASKS[category].format(index=index),
        "initial_state": DEFAULT_STATE.to_dict(), "trajectory": trajectory, "oracle_states": oracle,
    }


def generate_split() -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {"train": [], "test": []}
    index = 0
    for split, groups in (("train", TRAIN_STAGES), ("test", TEST_STAGES)):
        for category, stages in groups.items():
            for horizon_name, horizon, count in HORIZONS:
                for _ in range(count):
                    index += 1
                    output[split].append(make_sample(split, category, stages, horizon_name, horizon, index))
    return output


@dataclass(frozen=True)
class PredictionView:
    sample_id: str
    task: str
    actions: tuple[str, ...]
    observations: tuple[str, ...]


def mode_state(values: list[DelegationState]) -> DelegationState:
    counts = Counter(values)
    return max(counts, key=lambda value: (counts[value], tuple(value.to_dict().values())))


def fit_action_map(training: list[dict[str, Any]]) -> dict[str, DelegationState]:
    examples: dict[str, list[DelegationState]] = defaultdict(list)
    for sample in training:
        for event, encoded in zip(sample["trajectory"], sample["oracle_states"][1:]):
            examples[event["action"].lower()].append(DelegationState.from_dict(encoded))
    return {action: mode_state(values) for action, values in examples.items()}


def capability(action: str) -> str:
    value = action.lower()
    if re.search(r"\b(?:book|buy|purchase|finalize)\b", value):
        return "transaction"
    if re.search(r"\b(?:send|dispatch|publish)\b", value):
        return "communication"
    if re.search(r"\b(?:select|add|enter|compose|formulate|draft)\b", value):
        return "modify"
    return "observe"


def fit_capability_map(training: list[dict[str, Any]]) -> dict[str, DelegationState]:
    examples: dict[str, list[DelegationState]] = defaultdict(list)
    for sample in training:
        for event, encoded in zip(sample["trajectory"], sample["oracle_states"][1:]):
            examples[capability(event["action"])].append(DelegationState.from_dict(encoded))
    return {name: mode_state(values) for name, values in examples.items()}


def contextual_required(task: str, action: str) -> DelegationState:
    """Compose generic task effect and action phase into a delegation state."""
    cap = capability(action)
    communication_task = bool(re.search(r"\b(?:email|reply|support|calendar|invitation)\b", task, re.I))
    transaction_task = bool(re.search(r"\b(?:book|buy|reserve|flight|hotel|product)\b", task, re.I))
    if cap == "transaction" and transaction_task:
        return TRANSACTION
    if cap == "communication" and communication_task:
        return COMMUNICATION
    if cap == "modify":
        if transaction_task and re.search(r"\b(?:choose|select|add)\b", action, re.I):
            return PUBLIC
        if transaction_task:
            return USER_VIEW
        return WEB_DRAFT
    if transaction_task and re.search(r"\b(?:traveler|checkout|delivery|guest)\b", action, re.I):
        return USER_VIEW
    if communication_task and re.search(r"\b(?:history|availability|attendee|thread|response|draft)\b", action, re.I):
        return WEB_USER_VIEW
    return PUBLIC


def build_predictors(training: list[dict[str, Any]]) -> dict[str, Callable[[PredictionView], list[DelegationState]]]:
    action_map = fit_action_map(training)
    capability_map = fit_capability_map(training)

    def m0(view: PredictionView) -> list[DelegationState]:
        return [DEFAULT_STATE, *[action_map.get(action.lower(), DEFAULT_STATE) for action in view.actions]]

    def m1(view: PredictionView) -> list[DelegationState]:
        return [DEFAULT_STATE, *[capability_map.get(capability(action), DEFAULT_STATE) for action in view.actions]]

    def m2(view: PredictionView) -> list[DelegationState]:
        states = [DEFAULT_STATE]
        current = DEFAULT_STATE
        for action in view.actions:
            current = current.join(capability_map.get(capability(action), DEFAULT_STATE))
            states.append(current)
        return states

    def m3(view: PredictionView) -> list[DelegationState]:
        states = [DEFAULT_STATE]
        current = DEFAULT_STATE
        for action in view.actions:
            current = current.join(contextual_required(view.task, action))
            states.append(current)
        return states

    return {
        "M0_action_only": m0, "M1_capability_only": m1,
        "M2_history": m2, "M3_delegation_state_model": m3,
    }


def binary_f1(truth: list[bool], prediction: list[bool]) -> float:
    tp=sum(a and b for a,b in zip(truth,prediction)); fp=sum(not a and b for a,b in zip(truth,prediction)); fn=sum(a and not b for a,b in zip(truth,prediction))
    return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0


def evaluate(testing: list[dict[str, Any]], predictors: dict[str, Callable[[PredictionView], list[DelegationState]]]) -> tuple[list[dict[str, Any]], int]:
    output=[]; actual_count=0
    for method,predictor in predictors.items():
        exact=[]; actual=[]; predicted=[]
        for sample in testing:
            view=PredictionView(sample["id"],sample["task"],tuple(e["action"] for e in sample["trajectory"]),tuple(e["observation"] for e in sample["trajectory"]))
            states=predictor(view)
            # Test labels are evaluation-only and are accessed after prediction.
            oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
            for step in range(1,len(oracle)):
                exact.append(states[step]==oracle[step])
                actual.append(bool(state_transition(oracle[step-1],oracle[step])["changed"]))
                predicted.append(bool(state_transition(states[step-1],states[step])["changed"]))
        if method==next(iter(predictors)):
            actual_count=sum(actual)
        output.append({
            "method":method, "state_recovery_accuracy":round(mean(exact),4),
            "transition_detection_f1":round(binary_f1(actual,predicted),4),
            "test_states":len(exact),
        })
    return output,actual_count


def validate(split: dict[str,list[dict[str,Any]]], predictors: dict[str,Callable]) -> dict[str,Any]:
    train,test=split["train"],split["test"]
    train_actions={e["action"].lower() for s in train for e in s["trajectory"]}
    test_actions={e["action"].lower() for s in test for e in s["trajectory"]}
    if train_actions & test_actions:
        raise AssertionError(f"surface-action leakage: {sorted(train_actions & test_actions)}")
    train_states={tuple(value.values()) for s in train for value in s["oracle_states"]}
    test_states={tuple(value.values()) for s in test for value in s["oracle_states"]}
    if not test_states <= train_states:
        raise AssertionError("test contains delegation states absent from training")
    for name,predictor in predictors.items():
        source=inspect.getsource(predictor)
        if "oracle_states" in source or "required_state" in source:
            raise AssertionError(f"oracle lookup in predictor {name}")
    token_pattern=re.compile(r"[a-z]+")
    train_tokens={token for action in train_actions for token in token_pattern.findall(action)}
    test_tokens={token for action in test_actions for token in token_pattern.findall(action)}
    return {
        "train_actions":len(train_actions), "test_actions":len(test_actions),
        "shared_surface_actions":0, "train_state_types":len(train_states),
        "test_state_types":len(test_states), "test_states_covered_by_train":True,
        "shared_action_tokens":sorted(train_tokens & test_tokens),
        "test_action_token_unseen_rate":round(len(test_tokens-train_tokens)/len(test_tokens),4),
    }


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--benchmark-output",type=Path,default=ROOT/"benchmarks/delegationbench/compositional_split.json")
    parser.add_argument("--output",type=Path,default=ROOT/"results/delegationbench_compositional_split.csv")
    args=parser.parse_args()
    split=generate_split()
    predictors=build_predictors(split["train"])
    validation=validate(split,predictors)
    results,transitions=evaluate(split["test"],predictors)
    args.benchmark_output.parent.mkdir(parents=True,exist_ok=True)
    args.benchmark_output.write_text(json.dumps(split,indent=2),encoding="utf-8")
    write_csv(args.output,results)
    print(json.dumps({
        "training_categories":list(TRAIN_STAGES), "testing_categories":list(TEST_STAGES),
        "training_trajectories":len(split["train"]), "testing_trajectories":len(split["test"]),
        "test_transitions":transitions, "results":results, "validation":validation,
        "scope":"Synthetic lexical hard split; no real-world generalization claim.",
    },indent=2))


if __name__=="__main__":
    main()
