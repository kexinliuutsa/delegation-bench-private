#!/usr/bin/env python3
"""DelegationBench v0 baselines and state-evolution evaluation."""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.delegation_state import DEFAULT_STATE, DelegationState, directional_error, state_transition


def state(resource: str, operation: str, information: str, persistence: str, effect: str) -> DelegationState:
    return DelegationState(resource, operation, information, persistence, effect)


@dataclass(frozen=True)
class PredictionSample:
    """Label-free trajectory view provided to every baseline."""

    sample_id: str
    task: str
    actions: tuple[str, ...]
    observations: tuple[str, ...]


def action_state(action: str) -> DelegationState:
    """M0's action-only state lookup, with no task or history."""
    value = action.lower()
    if "delete" in value:
        return state("local", "delete", "private", "persistent", "irreversible")
    if "execute" in value:
        return state("local", "execute", "private", "session", "none")
    if "create" in value or "edit" in value:
        return state("local", "modify", "private", "session", "none")
    if value == "click submit":
        return state("website", "modify", "user_data", "persistent", "communication")
    if "account" in value or "profile" in value or "checkout" in value:
        operation = "modify" if "edit" in value else "observe"
        return state("account", operation, "user_data", "session", "none")
    if "conversation" in value or "response" in value:
        operation = "modify" if "draft" in value else "observe"
        return state("website", operation, "user_data", "session", "none")
    if "workspace" in value or "duplicate" in value or "manifest" in value:
        return state("local", "observe", "private", "temporary", "none")
    return state("website", "observe", "public", "temporary", "none")


def observable_capability(action: str) -> str:
    value = action.lower()
    if "delete" in value:
        return "delete"
    if "execute" in value:
        return "execute"
    if "submit" in value:
        return "submit"
    if re.search(r"\b(?:create|edit|draft)\b", value):
        return "modify"
    return "observe"


CAPABILITY_PROTOTYPES = {
    "observe": state("website", "observe", "public", "temporary", "none"),
    "modify": state("local", "modify", "private", "session", "none"),
    "execute": state("local", "execute", "private", "session", "none"),
    "delete": state("local", "delete", "private", "persistent", "irreversible"),
    "submit": state("website", "modify", "user_data", "persistent", "communication"),
}


def task_category(task: str) -> str:
    if re.search(r"\b(?:buy|purchase|pay|book)\b", task, re.I):
        return "purchase"
    if re.search(r"\b(?:send|message|email|contact|submit support)\b", task, re.I):
        return "communication"
    if re.search(r"\b(?:file|workspace|duplicate)\b", task, re.I):
        return "file_operation"
    if re.search(r"\b(?:account|profile|settings)\b", task, re.I):
        return "account_management"
    return "information_search"


def contextual_action_state(task: str, action: str) -> DelegationState:
    """Infer the current action state using task context, without oracle data."""
    category = task_category(task)
    value = action.lower()
    if category == "information_search":
        return state("website", "observe", "public", "temporary", "none")
    if category == "account_management":
        operation = "modify" if "edit" in value or "submit" in value else "observe"
        persistence = "persistent" if "submit" in value else "session"
        return state("account", operation, "user_data", persistence, "none")
    if category == "purchase":
        if "submit" in value:
            return state("account", "transaction", "user_data", "persistent", "financial")
        if "checkout" in value:
            return state("account", "observe", "user_data", "session", "none")
        return state("website", "observe", "public", "temporary", "none")
    if category == "communication":
        if "submit" in value:
            return state("external", "modify", "user_data", "persistent", "communication")
        if "conversation" in value or "response" in value:
            operation = "modify" if "draft" in value else "observe"
            return state("website", operation, "user_data", "session", "none")
        return state("website", "observe", "public", "temporary", "none")
    if "delete" in value:
        return state("local", "delete", "private", "persistent", "irreversible")
    if "execute" in value:
        return state("local", "execute", "private", "session", "none")
    if "create" in value:
        return state("local", "modify", "private", "session", "none")
    return state("local", "observe", "private", "temporary", "none")


def predict_m0(sample: PredictionSample) -> list[DelegationState]:
    return [DEFAULT_STATE, *[action_state(action) for action in sample.actions]]


def predict_m1(sample: PredictionSample) -> list[DelegationState]:
    return [DEFAULT_STATE, *[CAPABILITY_PROTOTYPES[observable_capability(action)] for action in sample.actions]]


def predict_m2(sample: PredictionSample) -> list[DelegationState]:
    predictions = [DEFAULT_STATE]
    current = DEFAULT_STATE
    for action in sample.actions:
        current = current.join(action_state(action))
        predictions.append(current)
    return predictions


def predict_m3(sample: PredictionSample) -> list[DelegationState]:
    predictions = [DEFAULT_STATE]
    current = DEFAULT_STATE
    for action in sample.actions:
        current = current.join(contextual_action_state(sample.task, action))
        predictions.append(current)
    return predictions


BASELINES: dict[str, Callable[[PredictionSample], list[DelegationState]]] = {
    "M0_action_only": predict_m0,
    "M1_capability_only": predict_m1,
    "M2_history_aggregation": predict_m2,
    "M3_delegation_state_model": predict_m3,
}


def leakage_audit() -> dict[str, Any]:
    offenders = []
    for name, predictor in BASELINES.items():
        source = inspect.getsource(predictor)
        if "oracle_states" in source or "required_state" in source:
            offenders.append(name)
    if offenders:
        raise AssertionError(f"oracle reference in predictor(s): {offenders}")
    return {
        "status": "pass", "predictor_oracle_access": [],
        "prediction_fields": ["id", "task", "trajectory.action", "trajectory.observation"],
    }


def binary_f1(truth: list[bool], predicted: list[bool]) -> float:
    tp = sum(a and b for a, b in zip(truth, predicted))
    fp = sum(not a and b for a, b in zip(truth, predicted))
    fn = sum(a and not b for a, b in zip(truth, predicted))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0


def evaluate(samples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows = []
    actual_transition_count = 0
    for baseline, predictor in BASELINES.items():
        exact: list[bool] = []
        actual_transitions: list[bool] = []
        predicted_transitions: list[bool] = []
        over_errors: list[float] = []
        under_errors: list[float] = []
        for encoded in samples:
            # Construct a fresh label-free object before prediction.
            view = PredictionSample(
                sample_id=encoded["id"], task=encoded["task"],
                actions=tuple(event["action"] for event in encoded["trajectory"]),
                observations=tuple(event["observation"] for event in encoded["trajectory"]),
            )
            predicted = predictor(view)
            # Oracle fields are accessed only after the prediction is complete.
            oracle = [DelegationState.from_dict(value) for value in encoded["oracle_states"]]
            if len(predicted) != len(oracle):
                raise AssertionError(f"prediction length mismatch for {baseline}/{encoded['id']}")
            for index in range(1, len(oracle)):
                exact.append(predicted[index] == oracle[index])
                actual_transitions.append(bool(state_transition(oracle[index-1], oracle[index])["changed"]))
                predicted_transitions.append(bool(state_transition(predicted[index-1], predicted[index])["changed"]))
                over, under = directional_error(predicted[index], oracle[index])
                over_errors.append(over)
                under_errors.append(under)
        if baseline == next(iter(BASELINES)):
            actual_transition_count = sum(actual_transitions)
        rows.append({
            "baseline": baseline,
            "input": {
                "M0_action_only": "current action",
                "M1_capability_only": "current observable capability",
                "M2_history_aggregation": "actions through current step",
                "M3_delegation_state_model": "task-conditioned inferred cumulative state",
            }[baseline],
            "state_recovery_accuracy": round(mean(exact), 4),
            "transition_detection_f1": round(binary_f1(actual_transitions, predicted_transitions), 4),
            "over_delegation_error": round(mean(over_errors), 4),
            "under_delegation_error": round(mean(under_errors), 4),
            "evaluated_states": len(exact),
        })
    return rows, actual_transition_count


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    metrics = (
        ("state_recovery_accuracy", "State recovery"),
        ("transition_detection_f1", "Transition F1"),
        ("over_delegation_error", "Over-delegation error"),
        ("under_delegation_error", "Under-delegation error"),
    )
    colors=("#64748b","#f59e0b","#8b5cf6","#2563eb")
    width,height=1050,590; left,right,top,bottom=80,30,65,105
    plot_w,plot_h=width-left-right,height-top-bottom
    group_w=plot_w/len(metrics); bar_w=group_w/(len(rows)+1)
    parts=[
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="525" y="28" text-anchor="middle" font-family="sans-serif" font-size="18">DelegationBench v0 baseline comparison</text>',
    ]
    for tick in range(0,11,2):
        value=tick/10; y=top+plot_h*(1-value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{value:.1f}</text>')
    for gi,(field,label) in enumerate(metrics):
        gx=left+gi*group_w
        for mi,row in enumerate(rows):
            value=float(row[field]); x=gx+(mi+.5)*bar_w; y=top+plot_h*(1-value)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w*.82:.1f}" height="{plot_h*value:.1f}" fill="{colors[mi]}"/>')
            parts.append(f'<text x="{x+bar_w*.41:.1f}" y="{y-5:.1f}" text-anchor="middle" font-family="sans-serif" font-size="9">{value:.2f}</text>')
        parts.append(f'<text x="{gx+group_w/2:.1f}" y="{top+plot_h+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{label}</text>')
    for index,row in enumerate(rows):
        x=left+index*225
        parts.append(f'<rect x="{x}" y="{height-38}" width="12" height="12" fill="{colors[index]}"/>')
        parts.append(f'<text x="{x+17}" y="{height-28}" font-family="sans-serif" font-size="11">{row["baseline"]}</text>')
    parts.extend([
        f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#111827"/>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=ROOT / "benchmarks/delegationbench/delegationbench_v0.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/delegationbench_summary.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/delegation_transition.svg")
    args = parser.parse_args()
    audit = leakage_audit()
    samples = json.loads(args.benchmark.read_text(encoding="utf-8"))
    rows, transitions = evaluate(samples)
    write_csv(args.output, rows)
    write_svg(args.plot, rows)
    print(json.dumps({
        "number_of_tasks": len(samples), "number_of_trajectories": len(samples),
        "number_of_transitions": transitions, "baseline_comparison": rows,
        "leakage_audit": audit,
        "scope": "Controlled benchmark construction; no real-world agent safety claim.",
    }, indent=2))


if __name__ == "__main__":
    main()
