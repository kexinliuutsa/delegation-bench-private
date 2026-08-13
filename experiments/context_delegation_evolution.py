#!/usr/bin/env python3
"""Experiment 23: context-aware delegation evolution.

C_t is an online symbolic execution-context estimate built only from task text
and the observable prefix. Training oracle transitions supervise predictors,
but evaluation oracle states are unavailable until all predictions are fixed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from delegation_evolution_model import payload as history_payload, payload_tokens as history_tokens
from delegation_inference_baselines import FullHistoryRetrieval, observable_capability, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from learned_delegation_transition import MultiLabelModel, delta_label, macro_f1
from models.delegation_state import DelegationState
from trigger_delegation_model import TriggerState, trigger_tokens
from trigger_graph_delegation_model import TriggerDependencyGraph, graph_tokens


METHODS = ("M0_current_state", "M1_flat_trigger", "M2_last_5_events", "M3_full_trajectory", "M4_trigger_graph", "M5_context_aware")

GOAL_PATTERNS = {
    "access": re.compile(r"\b(find|inspect|update|purchase|send|delete|report)\b", re.I),
    "inspect": re.compile(r"\b(find|inspect|report|purchase|delete)\b", re.I),
    "modify": re.compile(r"\b(update|change|draft|send)\b", re.I),
    "validate": re.compile(r"\b(delete|cleanup|validate|duplicate)\b", re.I),
    "transact": re.compile(r"\b(purchase|buy|book|pay)\b", re.I),
    "communicate": re.compile(r"\b(send|message|email|report)\b", re.I),
    "delete": re.compile(r"\b(delete|remove|cleanup)\b", re.I),
}
GOAL_COMPLETION = {
    "access": re.compile(r"\b(open|list|view|read)\b", re.I),
    "inspect": re.compile(r"\b(view|read|result|details|displayed|matching)\b", re.I),
    "modify": re.compile(r"\b(edit|update|draft|enter|create|stored)\b", re.I),
    "validate": re.compile(r"\b(validate|validation|review)\b", re.I),
    "transact": re.compile(r"\b(purchase|checkout|pay|book)\b", re.I),
    "communicate": re.compile(r"\b(message submitted|send|email|report(?:ed)?)\b", re.I),
    "delete": re.compile(r"\b(delete|removed|unlink)\b", re.I),
}
CONSTRAINT_PATTERNS = {
    "budget": re.compile(r"(?:\$\s*\d+|\bunder\b|\bat most\b)", re.I),
    "provided_content": re.compile(r"\bprovided\b", re.I),
    "duplicate_only": re.compile(r"\bduplicate\b", re.I),
    "specific_value": re.compile(r"\b(update|change).+\bto\b", re.I),
}
APPROVAL_PENDING = re.compile(r"\b(ask|approval required|confirm before|permission required)\b", re.I)
APPROVAL_GRANTED = re.compile(r"\b(approved|approval granted|confirmed|authorized)\b", re.I)


def normalize_action(action: str) -> str:
    return "_".join(re.findall(r"[a-z]+", action.lower())) or "unknown"


@dataclass
class ExecutionContextState:
    task: str
    step: int = 0
    task_goals: set[str] = field(default_factory=set)
    completed_goals: set[str] = field(default_factory=set)
    pending_constraints: set[str] = field(default_factory=set)
    resolved_constraints: set[str] = field(default_factory=set)
    pending_approvals: set[str] = field(default_factory=set)
    granted_approvals: set[str] = field(default_factory=set)
    seen_stages: list[str] = field(default_factory=list)
    current_stage: str = "start"
    stage_run_length: int = 0
    trigger: TriggerState = field(default_factory=TriggerState)

    def __post_init__(self) -> None:
        self.task_goals = {name for name, pattern in GOAL_PATTERNS.items() if pattern.search(self.task)}
        self.pending_constraints = {name for name, pattern in CONSTRAINT_PATTERNS.items() if pattern.search(self.task)}
        if APPROVAL_PENDING.search(self.task):
            self.pending_approvals.add("explicit_approval")

    def update(self, action: str, observation: str) -> None:
        self.step += 1
        combined = f"{action} {observation}"
        stage = normalize_action(action)
        if stage == self.current_stage:
            self.stage_run_length += 1
        else:
            self.current_stage = stage
            self.stage_run_length = 1
            if stage not in self.seen_stages:
                self.seen_stages.append(stage)
        for goal in self.task_goals:
            if GOAL_COMPLETION[goal].search(combined):
                self.completed_goals.add(goal)
        if "budget" in self.pending_constraints and re.search(r"\b(product|hotel|result|listing|matching)\b", combined, re.I):
            self.resolved_constraints.add("budget")
        if "provided_content" in self.pending_constraints and re.search(r"\b(draft|response|entered|stored)\b", combined, re.I):
            self.resolved_constraints.add("provided_content")
        if "duplicate_only" in self.pending_constraints and re.search(r"\b(duplicate candidates|duplicate report|manifest validation)\b", combined, re.I):
            self.resolved_constraints.add("duplicate_only")
        if "specific_value" in self.pending_constraints and re.search(r"\b(updated value entered|edit profile)\b", combined, re.I):
            self.resolved_constraints.add("specific_value")
        if APPROVAL_GRANTED.search(observation):
            self.granted_approvals.add("explicit_approval")
        self.trigger.update(action, observation)

    def snapshot(self) -> dict[str, Any]:
        trigger_snapshot = self.trigger.snapshot()
        boundaries = [item for item in trigger_snapshot["trigger_ages"] if item.startswith("boundary:")]
        recent_boundary = min(boundaries, key=lambda item: trigger_snapshot["trigger_ages"][item]) if boundaries else None
        return {
            "step": self.step,
            "progress_stage": self.current_stage,
            "stage_run_length": min(self.stage_run_length, 10),
            "completed_stage_count": len(self.seen_stages),
            "completed_goals": sorted(self.completed_goals),
            "unresolved_goals": sorted(self.task_goals - self.completed_goals),
            "pending_approvals": sorted(self.pending_approvals - self.granted_approvals),
            "granted_approvals": sorted(self.granted_approvals),
            "pending_constraints": sorted(self.pending_constraints - self.resolved_constraints),
            "resolved_constraints": sorted(self.resolved_constraints),
            "recent_capability_boundary": recent_boundary,
            "boundary_recency": trigger_snapshot["trigger_ages"].get(recent_boundary) if recent_boundary else None,
        }


def context_tokens(current: DelegationState, flat: TriggerState, context: ExecutionContextState) -> set[str]:
    tokens = trigger_tokens(current, flat.snapshot())
    snapshot = context.snapshot()
    tokens.update({
        f"context:stage={snapshot['progress_stage']}",
        f"context:stage-run={snapshot['stage_run_length']}",
        f"context:completed-stage-count={min(snapshot['completed_stage_count'], 8)}",
        f"context:recent-boundary={snapshot['recent_capability_boundary']}",
        f"context:boundary-recency={min(snapshot['boundary_recency'], 10) if snapshot['boundary_recency'] is not None else 'none'}",
    })
    for field_name in ("completed_goals", "unresolved_goals", "pending_approvals", "granted_approvals", "pending_constraints", "resolved_constraints"):
        tokens.update(f"context:{field_name}:{value}" for value in snapshot[field_name])
    return tokens


def features(method: str, current: DelegationState, view: Any, step: int, flat: TriggerState, graph: TriggerDependencyGraph, context: ExecutionContextState) -> set[str]:
    if method == "M0_current_state":
        return history_tokens(history_payload("M0_current_state", current, view, step, 0, 0))
    if method == "M1_flat_trigger":
        return trigger_tokens(current, flat.snapshot())
    if method == "M2_last_5_events":
        return history_tokens(history_payload("M2_last_5_events", current, view, step, 0, 0))
    if method == "M3_full_trajectory":
        return history_tokens(history_payload("M3_full_trajectory", current, view, step, 0, 0))
    if method == "M4_trigger_graph":
        return graph_tokens(current, graph.snapshot())
    if method == "M5_context_aware":
        return context_tokens(current, flat, context)
    raise ValueError(method)


def serialized_payload(method: str, current: DelegationState, view: Any, step: int, flat: TriggerState, graph: TriggerDependencyGraph, context: ExecutionContextState) -> dict[str, Any]:
    if method == "M0_current_state":
        return history_payload("M0_current_state", current, view, step, 0, 0)
    if method == "M1_flat_trigger":
        return {"current_delegation_state": current.to_dict(), "trigger_state": flat.snapshot()}
    if method == "M2_last_5_events":
        return history_payload("M2_last_5_events", current, view, step, 0, 0)
    if method == "M3_full_trajectory":
        return history_payload("M3_full_trajectory", current, view, step, 0, 0)
    if method == "M4_trigger_graph":
        return {"current_delegation_state": current.to_dict(), "trigger_dependency_graph": graph.snapshot()}
    if method == "M5_context_aware":
        return {"current_delegation_state": current.to_dict(), "trigger_state": flat.snapshot(), "execution_context": context.snapshot()}
    raise ValueError(method)


def build_training_data(training: list[dict[str, Any]]) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    documents = {method: [] for method in METHODS}
    labels = []
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        flat, graph, context = TriggerState(), TriggerDependencyGraph(), ExecutionContextState(view.task)
        for step in range(1, len(view.actions)):
            action, observation = view.actions[step - 1], view.observations[step - 1]
            flat.update(action, observation); graph.update(action, observation); context.update(action, observation)
            for method in METHODS:
                documents[method].append(features(method, oracle[step], view, step, flat, graph, context))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def evaluate(evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval, models: dict[str, MultiLabelModel]) -> list[dict[str, Any]]:
    buckets = defaultdict(lambda: {"truth": [], "predicted": [], "sizes": []})
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        flat, graph, context = TriggerState(), TriggerDependencyGraph(), ExecutionContextState(view.task)
        predictions = {method: [] for method in METHODS}; sizes = {method: [] for method in METHODS}
        for step in range(1, len(view.actions)):
            action, observation = view.actions[step - 1], view.observations[step - 1]
            flat.update(action, observation); graph.update(action, observation); context.update(action, observation)
            for method in METHODS:
                document = features(method, inferred[step], view, step, flat, graph, context)
                predictions[method].append(models[method].predict(document))
                value = serialized_payload(method, inferred[step], view, step, flat, graph, context)
                sizes[method].append(len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()))
        # Oracle transitions are evaluation-only and opened after prediction.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        horizon = len(view.actions)
        for method in METHODS:
            bucket = buckets[(method, horizon)]
            bucket["truth"].extend(truth); bucket["predicted"].extend(predictions[method]); bucket["sizes"].extend(sizes[method])
    return [{
        "method": method,
        "horizon": horizon,
        "transition_f1_macro": round(macro_f1(buckets[(method, horizon)]["truth"], buckets[(method, horizon)]["predicted"]), 4),
        "mean_serialized_context_bytes": round(mean(buckets[(method, horizon)]["sizes"]), 1),
        "prediction_events": len(buckets[(method, horizon)]["truth"]),
    } for method in METHODS for horizon in HORIZONS]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1080, 590; left, top, bottom, gap, panel_width = 75, 60, 80, 55, 450; plot_height = height - top - bottom
    colors = {"M0_current_state":"#64748b", "M1_flat_trigger":"#f59e0b", "M2_last_5_events":"#8b5cf6", "M3_full_trajectory":"#059669", "M4_trigger_graph":"#2563eb", "M5_context_aware":"#dc2626"}
    maximum = max(float(row["mean_serialized_context_bytes"]) for row in rows)
    panels = (("transition_f1_macro", "Transition macro F1", 1.0), ("mean_serialized_context_bytes", "Serialized context bytes", maximum))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="540" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">Context-aware delegation evolution by horizon</text>']
    for panel, (field, title, scale) in enumerate(panels):
        x0 = left + panel * (panel_width + gap)
        for tick in range(6):
            fraction = tick / 5; y = top + plot_height * (1 - fraction)
            parts += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_width}" y2="{y:.1f}" stroke="#e5e7eb"/>', f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction*scale:.1f}</text>']
        parts.append(f'<text x="{x0+panel_width/2}" y="{top-13}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method, color in colors.items():
            points = []
            for index, horizon in enumerate(HORIZONS):
                row = next(item for item in rows if item["method"] == method and int(item["horizon"]) == horizon)
                x = x0 + panel_width * index / (len(HORIZONS) - 1); y = top + plot_height * (1 - float(row[field]) / scale); points.append((x, y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>' for x, y in points)
        for index, horizon in enumerate(HORIZONS):
            x = x0 + panel_width * index / (len(HORIZONS) - 1); parts.append(f'<text x="{x:.1f}" y="{top+plot_height+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, (method, color) in enumerate(colors.items()):
        x = 70 + (index % 3) * 335; y = height - 38 + (index // 3) * 18
        parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>', f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{method}</text>']
    parts.append("</svg>"); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/context_delegation_results.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/context_delegation_horizon.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    documents, labels = build_training_data(training)
    models = {method: MultiLabelModel(documents[method], labels, "logistic") for method in METHODS}
    rows = evaluate(evaluation, state_model, models)
    write_csv(args.output, rows); write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training), "evaluation_trajectories": len(evaluation), "results": rows,
        "context_state": "online task goals, progress stage, approvals, constraints, and recent boundary",
        "leakage_audit": "C_t uses task and prefix events only; evaluation oracle states open after predictions.",
    }, indent=2))


if __name__ == "__main__":
    main()
