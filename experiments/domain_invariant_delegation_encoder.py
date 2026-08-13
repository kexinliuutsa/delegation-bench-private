#!/usr/bin/env python3
"""Experiment 26: domain-invariant semantic delegation encoder.

The semantic encoder is rule-based and never fitted on domains or oracle
states. Transition heads are trained on oracle deltas, but their inputs contain
only reconstructed state plus observable prefix representations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from context_delegation_evolution import ExecutionContextState, context_tokens
from delegation_generalization import hard_split_corpus
from delegation_inference_baselines import ActionMapper, FullHistoryRetrieval, observable_capability, sanitized_view, state_key, training_examples
from delegation_state_compression import HORIZONS
from learned_delegation_transition import MultiLabelModel, delta_label, macro_f1
from models.delegation_state import DEFAULT_STATE, DelegationState
from trigger_delegation_model import TriggerState


METHODS = ("M0_surface_action_state", "M1_capability_only", "M2_original_cdem", "M3_semantic_encoder_cdem")


@dataclass(frozen=True)
class SemanticPrimitive:
    resource: str
    operation: str
    effect: str

    def tokens(self) -> set[str]:
        return {f"semantic:resource={self.resource}", f"semantic:operation={self.operation}", f"semantic:effect={self.effect}"}


class SemanticDelegationEncoder:
    """Map observable text to domain-neutral delegation primitives."""

    TRANSACTION_TASK = re.compile(r"\b(book|buy|purchase|reserve|reservation|flight|hotel|product|order)\b", re.I)
    COMMUNICATION_TASK = re.compile(r"\b(send|email|reply|support|calendar|invitation|message)\b", re.I)

    def primitive(self, task: str, action: str, observation: str) -> SemanticPrimitive:
        text = f"{action} {observation}".lower()
        task_transaction = bool(self.TRANSACTION_TASK.search(task))
        task_communication = bool(self.COMMUNICATION_TASK.search(task)) and not task_transaction
        if re.search(r"\b(file|manifest|repository|repo)\b", text) or ("workspace" in text and re.search(r"\b(local|file|directory)\b", f"{task} {text}", re.I)):
            resource = "repository object" if re.search(r"\b(repository|repo)\b", text) else "local artifact"
        elif re.search(r"\b(send|sent|dispatch|dispatched|publish|invitation sent|message submitted)\b", text):
            resource = "communication channel"
        elif re.search(r"\b(guest|traveler|delivery|checkout|thread|history|attendee|availability|profile|mailbox|saved)\b", text):
            resource = "user data"
        else:
            resource = "external service"

        if re.search(r"\b(delete|deleted|remove|removed|unlink)\b", text):
            operation = "delete"
        elif re.search(r"\b(commit|committed|save changes)\b", text):
            operation = "commit"
        elif re.search(r"\b(execute|run|test|validation)\b", text):
            operation = "execute"
        elif (task_transaction and re.search(r"\b(book|buy|purchase|finalize reservation|order submitted|booking submitted|reservation submitted)\b", text)) or (task_communication and re.search(r"\b(send|sent|dispatch|dispatched|publish|submitted)\b", text)):
            operation = "submit"
        elif re.search(r"\b(compose|formulate|draft|edit|update|create)\b", text):
            operation = "modify"
        else:
            operation = "observe"

        if operation == "delete":
            effect = "irreversible change"
        elif operation == "submit" and task_transaction:
            effect = "external transaction"
        elif operation == "submit" and task_communication:
            effect = "external communication"
        elif operation == "commit":
            effect = "internal persistent"
        else:
            effect = "internal reversible"
        return SemanticPrimitive(resource, operation, effect)

    def required_state(self, task: str, primitive: SemanticPrimitive) -> DelegationState:
        transaction_task = bool(self.TRANSACTION_TASK.search(task))
        if primitive.resource == "local artifact" or primitive.resource == "repository object":
            resource = "local"; information = "private"
        elif primitive.resource == "communication channel":
            resource = "external"; information = "user_data"
        elif primitive.resource == "user data":
            resource = "account" if transaction_task else "website"; information = "user_data"
        else:
            resource = "website"; information = "public"
        if primitive.effect == "external transaction":
            operation, persistence, effect = "transaction", "persistent", "financial"
        elif primitive.effect == "external communication":
            operation, persistence, effect = "modify", "persistent", "communication"
        elif primitive.effect == "irreversible change":
            operation, persistence, effect = "delete", "persistent", "irreversible"
        elif primitive.effect == "internal persistent":
            operation, persistence, effect = "modify", "persistent", "none"
        else:
            operation = {"observe":"observe", "modify":"modify", "execute":"execute", "delete":"delete", "commit":"modify", "submit":"modify"}[primitive.operation]
            persistence = "session" if information == "user_data" or operation in {"modify", "execute"} else "temporary"
            effect = "none"
        return DelegationState(resource, operation, information, persistence, effect)

    def predict(self, view: Any) -> tuple[list[DelegationState], list[SemanticPrimitive]]:
        states = [DEFAULT_STATE]; primitives = []; current = DEFAULT_STATE
        for action, observation in zip(view.actions, view.observations):
            primitive = self.primitive(view.task, action, observation)
            current = current.join(self.required_state(view.task, primitive))
            primitives.append(primitive); states.append(current)
        return states, primitives


class CapabilityStateMapper:
    def __init__(self, training: list[dict[str, Any]]) -> None:
        grouped: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
        for sample in training:
            view = sanitized_view(sample)
            for action, encoded in zip(view.actions, sample["oracle_states"][1:]):
                grouped[observable_capability(action)][tuple(encoded[key] for key in encoded)] += 1
        self.mapping = {capability: counts.most_common(1)[0][0] for capability, counts in grouped.items()}
        all_counts = sum(grouped.values(), Counter())
        self.default = all_counts.most_common(1)[0][0]

    def predict(self, view: Any) -> list[DelegationState]:
        states = [DEFAULT_STATE]
        for action in view.actions:
            key = self.mapping.get(observable_capability(action), self.default)
            states.append(DelegationState(*key))
        return states


def reconstructed_states(training: list[dict[str, Any]]) -> dict[str, Any]:
    examples = training_examples(training)
    return {
        "M0_surface_action_state": ActionMapper(examples[0]),
        "M1_capability_only": CapabilityStateMapper(training),
        "M2_original_cdem": FullHistoryRetrieval(examples[2]),
        "M3_semantic_encoder_cdem": SemanticDelegationEncoder(),
    }


def predict_states(method: str, model: Any, view: Any) -> tuple[list[DelegationState], list[SemanticPrimitive] | None]:
    if method == "M3_semantic_encoder_cdem":
        return model.predict(view)
    return model.predict(view), None


def semantic_context_tokens(current: DelegationState, primitives: list[SemanticPrimitive], step: int) -> set[str]:
    current_primitive = primitives[step - 1]
    tokens = {f"state:{key}={value}" for key, value in current.to_dict().items()} | current_primitive.tokens()
    tokens.add(f"semantic:run={min(sum(item == current_primitive for item in reversed(primitives[:step])), 10)}")
    seen = []
    for primitive in primitives[:step]:
        signature = (primitive.resource, primitive.operation, primitive.effect)
        if signature not in seen:
            seen.append(signature)
    tokens.add(f"semantic:progress={min(len(seen), 8)}")
    for previous, following in zip(primitives[:step], primitives[1:step]):
        if previous != following:
            tokens.add(f"semantic:edge={previous.operation}->{following.operation}")
            tokens.add(f"semantic:effect-edge={previous.effect}->{following.effect}")
    return tokens


def transition_features(method: str, current: DelegationState, view: Any, step: int, primitives: list[SemanticPrimitive] | None, flat: TriggerState, context: ExecutionContextState) -> set[str]:
    state_tokens = {f"state:{key}={value}" for key, value in current.to_dict().items()}
    if method == "M0_surface_action_state":
        return state_tokens | {f"surface:{view.actions[step-1].lower()}"}
    if method == "M1_capability_only":
        return state_tokens | {f"capability:{observable_capability(view.actions[step-1])}"}
    if method == "M2_original_cdem":
        return context_tokens(current, flat, context)
    if method == "M3_semantic_encoder_cdem" and primitives is not None:
        return semantic_context_tokens(current, primitives, step)
    raise ValueError(method)


def build_transition_training(training: list[dict[str, Any]], state_models: dict[str, Any]) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    documents = {method: [] for method in METHODS}; labels = []
    for sample in training:
        view = sanitized_view(sample)
        all_states = {}; all_primitives = {}
        for method in METHODS:
            all_states[method], all_primitives[method] = predict_states(method, state_models[method], view)
        flat, context = TriggerState(), ExecutionContextState(view.task)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1, len(view.actions)):
            flat.update(view.actions[step-1], view.observations[step-1]); context.update(view.actions[step-1], view.observations[step-1])
            for method in METHODS:
                documents[method].append(transition_features(method, all_states[method][step], view, step, all_primitives[method], flat, context))
            labels.append(delta_label(oracle[step], oracle[step+1]))
    return documents, labels


def representation_tokens(method: str, view: Any, primitives: list[SemanticPrimitive] | None, step: int, flat: TriggerState, context: ExecutionContextState) -> set[str]:
    if method == "M0_surface_action_state": return {f"surface:{view.actions[step-1].lower()}"}
    if method == "M1_capability_only": return {f"capability:{observable_capability(view.actions[step-1])}"}
    if method == "M2_original_cdem": return {token for token in context_tokens(DEFAULT_STATE, flat, context) if not token.startswith("state:")}
    if primitives is not None: return {token for token in semantic_context_tokens(DEFAULT_STATE, primitives, step) if not token.startswith("state:")}
    raise ValueError(method)


def vocabulary_overlap(training: list[dict[str, Any]], evaluation: list[dict[str, Any]], method: str, encoder: SemanticDelegationEncoder) -> tuple[float, float]:
    vocabularies = []
    for samples in (training, evaluation):
        vocabulary = set()
        for sample in samples:
            view = sanitized_view(sample); _, primitives = encoder.predict(view); flat, context = TriggerState(), ExecutionContextState(view.task)
            for step in range(1, len(view.actions)):
                flat.update(view.actions[step-1], view.observations[step-1]); context.update(view.actions[step-1], view.observations[step-1])
                vocabulary.update(representation_tokens(method, view, primitives if method == "M3_semantic_encoder_cdem" else None, step, flat, context))
        vocabularies.append(vocabulary)
    train_vocab, test_vocab = vocabularies
    return len(train_vocab & test_vocab) / len(train_vocab | test_vocab), len(train_vocab & test_vocab) / len(test_vocab)


def evaluate(training: list[dict[str, Any]], evaluation: list[dict[str, Any]], state_models: dict[str, Any], transition_models: dict[str, MultiLabelModel]) -> list[dict[str, Any]]:
    buckets = defaultdict(lambda: {"state": [], "truth": [], "predicted": []})
    for sample in evaluation:
        view = sanitized_view(sample); all_states = {}; all_primitives = {}; predictions = {method: [] for method in METHODS}
        for method in METHODS:
            all_states[method], all_primitives[method] = predict_states(method, state_models[method], view)
        flat, context = TriggerState(), ExecutionContextState(view.task)
        for step in range(1, len(view.actions)):
            flat.update(view.actions[step-1], view.observations[step-1]); context.update(view.actions[step-1], view.observations[step-1])
            for method in METHODS:
                feature = transition_features(method, all_states[method][step], view, step, all_primitives[method], flat, context)
                predictions[method].append(transition_models[method].predict(feature))
        # Evaluation states and deltas are unavailable until predictions finish.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [delta_label(oracle[step], oracle[step+1]) for step in range(1, len(view.actions))]
        horizon = len(view.actions)
        for method in METHODS:
            bucket = buckets[(method, horizon)]
            bucket["state"].extend(all_states[method][step] == oracle[step] for step in range(1, len(view.actions)+1))
            bucket["truth"].extend(truth); bucket["predicted"].extend(predictions[method])
    encoder = SemanticDelegationEncoder(); overlap = {method: vocabulary_overlap(training, evaluation, method, encoder) for method in METHODS}
    return [{
        "method": method,
        "horizon": horizon,
        "state_recovery_accuracy": round(mean(buckets[(method,horizon)]["state"]), 4),
        "transition_f1_macro": round(macro_f1(buckets[(method,horizon)]["truth"], buckets[(method,horizon)]["predicted"]), 4),
        "representation_overlap_jaccard": round(overlap[method][0], 4),
        "test_representation_coverage": round(overlap[method][1], 4),
        "prediction_events": len(buckets[(method,horizon)]["truth"]),
    } for method in METHODS for horizon in HORIZONS]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width,height=1060,580;left,top,bottom,gap,panel_width=75,58,75,55,440;plot_height=height-top-bottom
    colors={"M0_surface_action_state":"#64748b","M1_capability_only":"#f59e0b","M2_original_cdem":"#2563eb","M3_semantic_encoder_cdem":"#dc2626"}
    panels=(("state_recovery_accuracy","State recovery"),("transition_f1_macro","Transition macro F1"));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="530" y="26" text-anchor="middle" font-family="sans-serif" font-size="18">Domain-invariant delegation encoding</text>']
    for panel,(field,title) in enumerate(panels):
        x0=left+panel*(panel_width+gap)
        for tick in range(6):
            value=tick/5;y=top+plot_height*(1-value);parts += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>']
        parts.append(f'<text x="{x0+panel_width/2}" y="{top-13}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method,color in colors.items():
            points=[]
            for index,horizon in enumerate(HORIZONS):
                row=next(item for item in rows if item["method"]==method and int(item["horizon"])==horizon);x=x0+panel_width*index/(len(HORIZONS)-1);y=top+plot_height*(1-float(row[field]));points.append((x,y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>');parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>' for x,y in points)
        for index,horizon in enumerate(HORIZONS):
            x=x0+panel_width*index/(len(HORIZONS)-1);parts.append(f'<text x="{x:.1f}" y="{top+plot_height+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index,(method,color) in enumerate(colors.items()):
        x=75+index*245;parts += [f'<rect x="{x}" y="{height-29}" width="12" height="12" fill="{color}"/>',f'<text x="{x+17}" y="{height-19}" font-family="sans-serif" font-size="9">{method}</text>']
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/domain_invariant_delegation.csv');parser.add_argument('--plot',type=Path,default=ROOT/'results/domain_invariant_delegation.svg');args=parser.parse_args()
    training,evaluation=hard_split_corpus();state_models=reconstructed_states(training);documents,labels=build_transition_training(training,state_models);transition_models={method:MultiLabelModel(documents[method],labels,'logistic') for method in METHODS};rows=evaluate(training,evaluation,state_models,transition_models);write_csv(args.output,rows);write_svg(args.plot,rows)
    print(json.dumps({'training_trajectories':len(training),'evaluation_trajectories':len(evaluation),'results':rows,'semantic_taxonomy':{'resource':['local artifact','repository object','external service','user data','communication channel'],'operation':['observe','modify','execute','submit','commit','delete'],'effect':['internal reversible','internal persistent','external communication','external transaction','irreversible change']},'leakage_audit':'Semantic encoder uses task/action/observation prefix only; domain labels and evaluation oracles are unavailable during inference.'},indent=2))


if __name__=='__main__':main()
