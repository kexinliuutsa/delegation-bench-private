#!/usr/bin/env python3
"""Experiment 24: component ablation of context-aware delegation evolution.

Each representation is constructed from task text and the observable prefix.
Evaluation oracle states are opened only after all ablation predictions for a
trajectory have been fixed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from context_delegation_evolution import ExecutionContextState
from delegation_inference_baselines import FullHistoryRetrieval, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from learned_delegation_transition import MultiLabelModel, delta_label, macro_f1
from models.delegation_state import DelegationState
from trigger_delegation_model import TriggerState


COMPONENTS = (
    "task_stage",
    "completed_goals",
    "unresolved_goals",
    "constraints",
    "approval_status",
    "capability_boundary_history",
    "trigger_state",
)
ABLATIONS: dict[str, frozenset[str]] = {
    "A0_full_context": frozenset(),
    "A1_remove_task_stage": frozenset({"task_stage"}),
    "A2_remove_completed_goals": frozenset({"completed_goals"}),
    "A3_remove_unresolved_goals": frozenset({"unresolved_goals"}),
    "A4_remove_constraints": frozenset({"constraints"}),
    "A5_remove_approval_status": frozenset({"approval_status"}),
    "A6_remove_capability_boundary_history": frozenset({"capability_boundary_history"}),
    "A7_remove_trigger_state": frozenset({"trigger_state"}),
    "A8_remove_progress_information": frozenset({"task_stage", "completed_goals", "unresolved_goals"}),
    "A9_remove_authorization_information": frozenset({"constraints", "approval_status"}),
    "A10_remove_trigger_information": frozenset({"capability_boundary_history", "trigger_state"}),
}


def separated_trigger_snapshot(trigger: TriggerState) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = trigger.snapshot()
    observation_ages = {key: age for key, age in snapshot["trigger_ages"].items() if key.startswith("observation:")}
    boundary_ages = {key: age for key, age in snapshot["trigger_ages"].items() if key.startswith("boundary:")}
    observation_candidates = [item for item in snapshot["recent_transition_candidates"] if item["kind"].startswith("observation:")]
    boundary_candidates = [item for item in snapshot["recent_transition_candidates"] if item["kind"].startswith("boundary:")]
    trigger_part = {
        "current_capability": snapshot["current_capability"],
        "current_domain": snapshot["current_domain"],
        "current_reversibility": snapshot["current_reversibility"],
        "observation_trigger_counts": snapshot["observation_trigger_counts"],
        "observation_trigger_ages": observation_ages,
        "recent_observation_candidates": observation_candidates,
    }
    boundary_part = {
        "capability_boundary_counts": snapshot["capability_boundary_counts"],
        "boundary_ages": boundary_ages,
        "recent_boundary_candidates": boundary_candidates,
    }
    return trigger_part, boundary_part


def component_payload(current: DelegationState, context: ExecutionContextState, removed: frozenset[str]) -> dict[str, Any]:
    snapshot = context.snapshot()
    trigger_part, boundary_part = separated_trigger_snapshot(context.trigger)
    components: dict[str, Any] = {}
    if "task_stage" not in removed:
        components["task_stage"] = {
            "progress_stage": snapshot["progress_stage"],
            "stage_run_length": snapshot["stage_run_length"],
            "completed_stage_count": snapshot["completed_stage_count"],
        }
    if "completed_goals" not in removed:
        components["completed_goals"] = snapshot["completed_goals"]
    if "unresolved_goals" not in removed:
        components["unresolved_goals"] = snapshot["unresolved_goals"]
    if "constraints" not in removed:
        components["constraints"] = {
            "pending": snapshot["pending_constraints"],
            "resolved": snapshot["resolved_constraints"],
        }
    if "approval_status" not in removed:
        components["approval_status"] = {
            "pending": snapshot["pending_approvals"],
            "granted": snapshot["granted_approvals"],
        }
    if "capability_boundary_history" not in removed:
        components["capability_boundary_history"] = boundary_part
    if "trigger_state" not in removed:
        components["trigger_state"] = trigger_part
    return {"current_delegation_state": current.to_dict(), "execution_context": components}


def component_tokens(current: DelegationState, context: ExecutionContextState, removed: frozenset[str]) -> set[str]:
    """Match Experiment 23's full feature vocabulary, then remove aliases."""
    tokens = {f"state:{dimension}={value}" for dimension, value in current.to_dict().items()}
    snapshot = context.snapshot()
    trigger = context.trigger.snapshot()
    if "trigger_state" not in removed:
        tokens.update({
            f"trigger:capability={trigger['current_capability']}",
            f"trigger:domain={trigger['current_domain']}",
            f"trigger:reversibility={trigger['current_reversibility']}",
            f"trigger:step-bin={min(trigger['step'], 20)}",
        })
        for kind, count in trigger["observation_trigger_counts"].items():
            tokens.add(f"trigger:observation:{kind}:count={min(count, 5)}")
        for kind, age in trigger["trigger_ages"].items():
            if kind.startswith("observation:"):
                tokens.add(f"trigger:last:{kind}:age={min(age, 10)}")
        for rank, candidate in enumerate(reversed(trigger["recent_transition_candidates"]), 1):
            if candidate["kind"].startswith("observation:"):
                tokens.add(f"trigger:candidate-{rank}:{candidate['kind']}:age={min(candidate['age'], 10)}")
    if "capability_boundary_history" not in removed:
        for kind, count in trigger["capability_boundary_counts"].items():
            tokens.add(f"trigger:boundary:{kind}:count={min(count, 5)}")
        for kind, age in trigger["trigger_ages"].items():
            if kind.startswith("boundary:"):
                tokens.add(f"trigger:last:{kind}:age={min(age, 10)}")
        for rank, candidate in enumerate(reversed(trigger["recent_transition_candidates"]), 1):
            if candidate["kind"].startswith("boundary:"):
                tokens.add(f"trigger:candidate-{rank}:{candidate['kind']}:age={min(candidate['age'], 10)}")
        tokens.add(f"context:recent-boundary={snapshot['recent_capability_boundary']}")
        boundary_recency = min(snapshot["boundary_recency"], 10) if snapshot["boundary_recency"] is not None else "none"
        tokens.add(f"context:boundary-recency={boundary_recency}")
    if "task_stage" not in removed:
        tokens.update({
            f"context:stage={snapshot['progress_stage']}",
            f"context:stage-run={snapshot['stage_run_length']}",
            f"context:completed-stage-count={min(snapshot['completed_stage_count'], 8)}",
        })
    if "completed_goals" not in removed:
        tokens.update(f"context:completed_goals:{value}" for value in snapshot["completed_goals"])
    if "unresolved_goals" not in removed:
        tokens.update(f"context:unresolved_goals:{value}" for value in snapshot["unresolved_goals"])
    if "constraints" not in removed:
        tokens.update(f"context:pending_constraints:{value}" for value in snapshot["pending_constraints"])
        tokens.update(f"context:resolved_constraints:{value}" for value in snapshot["resolved_constraints"])
    if "approval_status" not in removed:
        tokens.update(f"context:pending_approvals:{value}" for value in snapshot["pending_approvals"])
        tokens.update(f"context:granted_approvals:{value}" for value in snapshot["granted_approvals"])
    return tokens


def build_training_data(training: list[dict[str, Any]]) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    documents = {name: [] for name in ABLATIONS}
    labels = []
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        context = ExecutionContextState(view.task)
        for step in range(1, len(view.actions)):
            context.update(view.actions[step - 1], view.observations[step - 1])
            for name, removed in ABLATIONS.items():
                documents[name].append(component_tokens(oracle[step], context, removed))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def evaluate(evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval, models: dict[str, MultiLabelModel]) -> list[dict[str, Any]]:
    buckets = defaultdict(lambda: {"truth": [], "predicted": [], "sizes": []})
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        context = ExecutionContextState(view.task)
        predictions = {name: [] for name in ABLATIONS}; sizes = {name: [] for name in ABLATIONS}
        for step in range(1, len(view.actions)):
            context.update(view.actions[step - 1], view.observations[step - 1])
            for name, removed in ABLATIONS.items():
                payload = component_payload(inferred[step], context, removed)
                predictions[name].append(models[name].predict(component_tokens(inferred[step], context, removed)))
                sizes[name].append(len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()))
        # Labels are unavailable until all ablation predictions are complete.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        horizon = len(view.actions)
        for name in ABLATIONS:
            bucket = buckets[(name, horizon)]
            bucket["truth"].extend(truth); bucket["predicted"].extend(predictions[name]); bucket["sizes"].extend(sizes[name])
    rows = []
    for name, removed in ABLATIONS.items():
        for horizon in HORIZONS:
            data = buckets[(name, horizon)]
            rows.append({
                "ablation": name,
                "removed_components": "+".join(sorted(removed)) if removed else "none",
                "horizon": horizon,
                "transition_f1_macro": round(macro_f1(data["truth"], data["predicted"]), 4),
                "mean_serialized_context_bytes": round(mean(data["sizes"]), 1),
                "prediction_events": len(data["truth"]),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1180, 690; left, top, plot_height, plot_width = 80, 55, 500, 1040
    colors = ["#111827", "#ef4444", "#f97316", "#eab308", "#84cc16", "#10b981", "#06b6d4", "#3b82f6", "#8b5cf6", "#d946ef", "#ec4899"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="590" y="26" text-anchor="middle" font-family="sans-serif" font-size="18">Context component ablation</text>']
    for tick in range(6):
        value = tick / 5; y = top + plot_height * (1 - value)
        parts += [f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>', f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>']
    for ablation_index, name in enumerate(ABLATIONS):
        points = []
        for horizon_index, horizon in enumerate(HORIZONS):
            row = next(item for item in rows if item["ablation"] == name and int(item["horizon"]) == horizon)
            x = left + plot_width * horizon_index / (len(HORIZONS) - 1); y = top + plot_height * (1 - float(row["transition_f1_macro"])); points.append((x, y))
        color = colors[ablation_index]
        parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{3 if ablation_index == 0 else 1.8}"/>')
        parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>' for x, y in points)
    for index, horizon in enumerate(HORIZONS):
        x = left + plot_width * index / (len(HORIZONS) - 1); parts.append(f'<text x="{x:.1f}" y="{top+plot_height+22}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, name in enumerate(ABLATIONS):
        column = index // 6; row = index % 6; x = 80 + column * 545; y = 605 + row * 14
        parts += [f'<rect x="{x}" y="{y-9}" width="11" height="11" fill="{colors[index]}"/>', f'<text x="{x+16}" y="{y}" font-family="sans-serif" font-size="9">{name}</text>']
    parts.append("</svg>"); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/context_component_ablation.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/context_component_ablation.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    documents, labels = build_training_data(training)
    models = {name: MultiLabelModel(documents[name], labels, "logistic") for name in ABLATIONS}
    rows = evaluate(evaluation, state_model, models)
    write_csv(args.output, rows); write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training), "evaluation_trajectories": len(evaluation), "ablations": len(ABLATIONS), "results": rows,
        "separation_audit": "Boundary fields are excluded from trigger_state so component removals do not retain aliases.",
        "leakage_audit": "All contexts use observable prefixes; evaluation oracles open after predictions.",
    }, indent=2))


if __name__ == "__main__":
    main()
