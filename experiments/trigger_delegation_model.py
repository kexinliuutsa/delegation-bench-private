#!/usr/bin/env python3
"""Experiment 21: trigger-aware delegation evolution prediction.

The trigger state is updated online from actions, observations, and observable
capabilities.  Evaluation oracle states are opened only after every prediction
for a trajectory has been fixed.  Training labels supervise only the transition
heads; they are never inputs to the trigger extractor or evaluation predictors.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from delegation_evolution_model import (
    PhaseEncoder,
    PhaseTransitionModel,
    fit_phases,
    hashed_vector,
    payload as dem_payload,
    payload_tokens as dem_payload_tokens,
)
from delegation_inference_baselines import FullHistoryRetrieval, observable_capability, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from learned_delegation_transition import MultiLabelModel, delta_label, macro_f1
from models.delegation_state import DelegationState


BASE_METHODS = ("M0_current_state", "M1_state_task", "M2_last_5_events", "M3_full_trajectory", "M4_phase_dem")
METHODS = (*BASE_METHODS, "M5_trigger_aware")
RECENT_CANDIDATES = 3

OBSERVATION_PATTERNS = {
    "error": re.compile(r"\b(error|failed|failure|invalid|denied|unavailable|exception)\b", re.I),
    "approval": re.compile(r"\b(approve|approval|confirm|confirmation|consent|permission|authorized)\b", re.I),
    "environment": re.compile(r"\b(installed|dependency|environment|runtime|package|configuration|configured)\b", re.I),
    "authentication": re.compile(r"\b(login|log in|sign in|authenticate|authentication|credential|password|token|required)\b", re.I),
}


def capability_class(action: str, capability: str) -> tuple[str, str]:
    text = action.lower()
    external = bool(re.search(r"\b(send|email|message|publish|push|upload|remote|api|book|buy|purchase|pay|checkout)\b", text))
    irreversible = capability in {"delete", "transaction"} or bool(re.search(r"\b(delete|remove|pay|purchase|book|publish)\b", text))
    return ("external" if external else "internal", "irreversible" if irreversible else "reversible")


def boundary_events(previous: str | None, current: str, previous_class: tuple[str, str] | None, current_class: tuple[str, str]) -> list[str]:
    events = []
    if previous == "observe" and current == "modify":
        events.append("read_to_write")
    if previous == "modify" and current == "execute":
        events.append("write_to_execute")
    if previous_class and previous_class[0] == "internal" and current_class[0] == "external":
        events.append("internal_to_external")
    if previous_class and previous_class[1] == "reversible" and current_class[1] == "irreversible":
        events.append("reversible_to_irreversible")
    return events


@dataclass
class TriggerState:
    step: int = 0
    previous_capability: str | None = None
    previous_class: tuple[str, str] | None = None
    observation_counts: Counter[str] = field(default_factory=Counter)
    boundary_counts: Counter[str] = field(default_factory=Counter)
    last_seen: dict[str, int] = field(default_factory=dict)
    candidates: deque[tuple[int, str]] = field(default_factory=lambda: deque(maxlen=RECENT_CANDIDATES))

    def update(self, action: str, observation: str) -> None:
        self.step += 1
        capability = observable_capability(action)
        current_class = capability_class(action, capability)
        observed = [name for name, pattern in OBSERVATION_PATTERNS.items() if pattern.search(observation)]
        boundaries = boundary_events(self.previous_capability, capability, self.previous_class, current_class)
        for kind in observed:
            key = f"observation:{kind}"
            self.observation_counts[kind] += 1
            self.last_seen[key] = self.step
            self.candidates.append((self.step, key))
        for kind in boundaries:
            key = f"boundary:{kind}"
            self.boundary_counts[kind] += 1
            self.last_seen[key] = self.step
            self.candidates.append((self.step, key))
        self.previous_capability = capability
        self.previous_class = current_class

    def snapshot(self) -> dict[str, Any]:
        ages = {name: min(self.step - seen, 20) for name, seen in sorted(self.last_seen.items())}
        candidates = [{"kind": kind, "age": self.step - seen} for seen, kind in self.candidates]
        return {
            "step": self.step,
            "current_capability": self.previous_capability,
            "current_domain": self.previous_class[0] if self.previous_class else None,
            "current_reversibility": self.previous_class[1] if self.previous_class else None,
            "observation_trigger_counts": dict(sorted(self.observation_counts.items())),
            "capability_boundary_counts": dict(sorted(self.boundary_counts.items())),
            "trigger_ages": ages,
            "recent_transition_candidates": candidates,
        }


def trigger_tokens(state: DelegationState, snapshot: dict[str, Any]) -> set[str]:
    tokens = {f"state:{dimension}={value}" for dimension, value in state.to_dict().items()}
    tokens.update({
        f"trigger:capability={snapshot['current_capability']}",
        f"trigger:domain={snapshot['current_domain']}",
        f"trigger:reversibility={snapshot['current_reversibility']}",
        f"trigger:step-bin={min(snapshot['step'], 20)}",
    })
    for kind, count in snapshot["observation_trigger_counts"].items():
        tokens.add(f"trigger:observation:{kind}:count={min(count, 5)}")
    for kind, count in snapshot["capability_boundary_counts"].items():
        tokens.add(f"trigger:boundary:{kind}:count={min(count, 5)}")
    for kind, age in snapshot["trigger_ages"].items():
        tokens.add(f"trigger:last:{kind}:age={min(age, 10)}")
    for rank, candidate in enumerate(reversed(snapshot["recent_transition_candidates"]), 1):
        tokens.add(f"trigger:candidate-{rank}:{candidate['kind']}:age={min(candidate['age'], 10)}")
    return tokens


def phase_features(state: DelegationState, view: Any, step: int, encoder: PhaseEncoder, phase_model: PhaseTransitionModel) -> set[str]:
    phase = encoder.encode(hashed_vector(view, step))
    following = phase_model.predict(phase, observable_capability(view.actions[step - 1]))
    payload = dem_payload("M4_dem", state, view, step, phase, following)
    return dem_payload_tokens(payload)


def baseline_features(method: str, state: DelegationState, view: Any, step: int, encoder: PhaseEncoder, phase_model: PhaseTransitionModel) -> set[str]:
    if method == "M4_phase_dem":
        return phase_features(state, view, step, encoder, phase_model)
    return dem_payload_tokens(dem_payload(method, state, view, step, 0, 0))


def build_training_data(training: list[dict[str, Any]], encoder: PhaseEncoder, phase_model: PhaseTransitionModel) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    documents = {method: [] for method in METHODS}
    labels: list[tuple[int, ...]] = []
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        trigger = TriggerState()
        for step in range(1, len(view.actions)):
            trigger.update(view.actions[step - 1], view.observations[step - 1])
            for method in BASE_METHODS:
                documents[method].append(baseline_features(method, oracle[step], view, step, encoder, phase_model))
            documents["M5_trigger_aware"].append(trigger_tokens(oracle[step], trigger.snapshot()))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def evaluate(evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval, encoder: PhaseEncoder, phase_model: PhaseTransitionModel, models: dict[str, MultiLabelModel]) -> list[dict[str, Any]]:
    buckets = defaultdict(lambda: {"truth": [], "predicted": [], "context_sizes": [], "trigger_sizes": []})
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred_states = state_model.predict(view)
        trigger = TriggerState()
        predictions = {method: [] for method in METHODS}
        context_sizes = {method: [] for method in METHODS}
        trigger_sizes = []
        for step in range(1, len(view.actions)):
            trigger.update(view.actions[step - 1], view.observations[step - 1])
            snapshot = trigger.snapshot()
            trigger_size = len(json.dumps(snapshot, separators=(",", ":"), sort_keys=True).encode())
            trigger_sizes.append(trigger_size)
            for method in BASE_METHODS:
                features = baseline_features(method, inferred_states[step], view, step, encoder, phase_model)
                if method == "M4_phase_dem":
                    phase = encoder.encode(hashed_vector(view, step))
                    following = phase_model.predict(phase, observable_capability(view.actions[step - 1]))
                    value = dem_payload("M4_dem", inferred_states[step], view, step, phase, following)
                else:
                    value = dem_payload(method, inferred_states[step], view, step, 0, 0)
                context_sizes[method].append(len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()))
                predictions[method].append(models[method].predict(features))
            trigger_payload = {"current_delegation_state": inferred_states[step].to_dict(), "trigger_state": snapshot}
            context_sizes["M5_trigger_aware"].append(len(json.dumps(trigger_payload, separators=(",", ":"), sort_keys=True).encode()))
            predictions["M5_trigger_aware"].append(models["M5_trigger_aware"].predict(trigger_tokens(inferred_states[step], snapshot)))

        # Evaluation labels are deliberately opened after every prediction.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        horizon = len(view.actions)
        for method in METHODS:
            bucket = buckets[(method, horizon)]
            bucket["truth"].extend(truth)
            bucket["predicted"].extend(predictions[method])
            bucket["context_sizes"].extend(context_sizes[method])
            if method == "M5_trigger_aware":
                bucket["trigger_sizes"].extend(trigger_sizes)

    rows = []
    for method in METHODS:
        for horizon in HORIZONS:
            data = buckets[(method, horizon)]
            rows.append({
                "method": method,
                "horizon": horizon,
                "transition_f1_macro": round(macro_f1(data["truth"], data["predicted"]), 4),
                "mean_serialized_context_bytes": round(mean(data["context_sizes"]), 1),
                "mean_trigger_state_bytes": round(mean(data["trigger_sizes"]), 1) if data["trigger_sizes"] else "",
                "prediction_events": len(data["truth"]),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1080, 590
    left, top, bottom, gap = 75, 60, 80, 55
    panel_width = 450
    plot_height = height - top - bottom
    colors = {"M0_current_state":"#64748b", "M1_state_task":"#f59e0b", "M2_last_5_events":"#8b5cf6", "M3_full_trajectory":"#059669", "M4_phase_dem":"#2563eb", "M5_trigger_aware":"#dc2626"}
    maximum_size = max(float(row["mean_serialized_context_bytes"]) for row in rows)
    panels = (("transition_f1_macro", "Transition macro F1", 1.0), ("mean_serialized_context_bytes", "Serialized context bytes", maximum_size))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="540" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">Trigger-aware delegation model by horizon</text>']
    for panel_index, (field, title, scale) in enumerate(panels):
        x0 = left + panel_index * (panel_width + gap)
        for tick in range(6):
            fraction = tick / 5
            y = top + plot_height * (1 - fraction)
            parts += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_width}" y2="{y:.1f}" stroke="#e5e7eb"/>', f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction*scale:.1f}</text>']
        parts.append(f'<text x="{x0+panel_width/2:.1f}" y="{top-13}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method, color in colors.items():
            points = []
            for index, horizon in enumerate(HORIZONS):
                row = next(item for item in rows if item["method"] == method and item["horizon"] == horizon)
                x = x0 + panel_width * index / (len(HORIZONS) - 1)
                y = top + plot_height * (1 - float(row[field]) / scale)
                points.append((x, y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>' for x, y in points)
        for index, horizon in enumerate(HORIZONS):
            x = x0 + panel_width * index / (len(HORIZONS) - 1)
            parts.append(f'<text x="{x:.1f}" y="{top+plot_height+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, (method, color) in enumerate(colors.items()):
        x = 70 + (index % 3) * 335
        y = height - 38 + (index // 3) * 18
        parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>', f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{method}</text>']
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/trigger_model_results.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/trigger_model_horizon.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    encoder, phase_model = fit_phases(training)
    documents, labels = build_training_data(training, encoder, phase_model)
    models = {method: MultiLabelModel(documents[method], labels, "logistic") for method in METHODS}
    rows = evaluate(evaluation, state_model, encoder, phase_model, models)
    write_csv(args.output, rows)
    write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training),
        "evaluation_trajectories": len(evaluation),
        "results": rows,
        "trigger_state": "online bounded observable-event summary",
        "leakage_audit": "No future events or oracle states enter prediction; evaluation labels open after trajectory predictions.",
    }, indent=2))


if __name__ == "__main__":
    main()
