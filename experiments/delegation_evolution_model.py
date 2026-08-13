#!/usr/bin/env python3
"""Delegation Evolution Model (DEM): learned latent execution phases.

The phase encoder is fit without delegation labels from observable training
prefixes. A phase-transition table estimates P(z_(t+1) | z_t, capability_t).
The supervised delegation head uses inferred D_t and latent phase features.
Evaluation labels are opened only after all prefix predictions are complete.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from delegation_inference_baselines import FullHistoryRetrieval, observable_capability, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from learned_delegation_transition import DIMENSIONS, MultiLabelModel, delta_label, macro_f1
from models.delegation_state import DelegationState


PHASES = 8
HASH_DIMENSIONS = 128
KMEANS_ITERATIONS = 8


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def stable_index(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big") % HASH_DIMENSIONS


def prefix_tokens(view: Any, step: int) -> list[str]:
    tokens = [f"task:{token}" for token in words(view.task)]
    capabilities = [observable_capability(action) for action in view.actions[:step]]
    tokens.extend(f"capability-count:{name}:{min(count, 10)}" for name, count in Counter(capabilities).items())
    tokens.append(f"last-capability:{capabilities[-1]}")
    tokens.append(f"step-bin:{min(step, 20)}")
    repeated = 1
    while repeated < step and view.actions[step - repeated - 1] == view.actions[step - 1]:
        repeated += 1
    tokens.append(f"repeat-bin:{min(repeated, 10)}")
    for offset in range(max(0, step - 2), step):
        relative = step - offset
        tokens.extend(f"action-{relative}:{token}" for token in words(view.actions[offset]))
        tokens.extend(f"observation-{relative}:{token}" for token in words(view.observations[offset]))
    return tokens


def hashed_vector(view: Any, step: int) -> list[float]:
    vector = [0.0] * HASH_DIMENSIONS
    for token in prefix_tokens(view, step):
        vector[stable_index(token)] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def squared_distance(left: list[float], right: list[float]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right))


class PhaseEncoder:
    def __init__(self, phase_count: int = PHASES) -> None:
        self.phase_count = phase_count
        self.centroids: list[list[float]] = []

    def fit(self, vectors: list[list[float]]) -> None:
        if len(vectors) < self.phase_count:
            raise ValueError("not enough prefixes for phase clustering")
        # Deterministic spread initialization; no oracle or category labels.
        self.centroids = [vectors[round(index * (len(vectors) - 1) / (self.phase_count - 1))][:] for index in range(self.phase_count)]
        assignments = [-1] * len(vectors)
        for _ in range(KMEANS_ITERATIONS):
            updated = [min(range(self.phase_count), key=lambda phase: squared_distance(vector, self.centroids[phase])) for vector in vectors]
            if updated == assignments:
                break
            assignments = updated
            sums = [[0.0] * HASH_DIMENSIONS for _ in range(self.phase_count)]
            counts = Counter(assignments)
            for vector, phase in zip(vectors, assignments):
                for index, value in enumerate(vector):
                    sums[phase][index] += value
            for phase in range(self.phase_count):
                if counts[phase]:
                    self.centroids[phase] = [value / counts[phase] for value in sums[phase]]

    def encode(self, vector: list[float]) -> int:
        if not self.centroids:
            raise RuntimeError("phase encoder not fitted")
        return min(range(self.phase_count), key=lambda phase: squared_distance(vector, self.centroids[phase]))


class PhaseTransitionModel:
    def __init__(self) -> None:
        self.conditioned: dict[tuple[int, str], Counter[int]] = defaultdict(Counter)
        self.phase_only: dict[int, Counter[int]] = defaultdict(Counter)
        self.global_counts: Counter[int] = Counter()

    def fit(self, sequences: list[tuple[list[int], list[str]]]) -> None:
        for phases, capabilities in sequences:
            for index in range(len(phases) - 1):
                current, future = phases[index], phases[index + 1]
                self.conditioned[(current, capabilities[index])][future] += 1
                self.phase_only[current][future] += 1
                self.global_counts[future] += 1

    def predict(self, phase: int, capability: str) -> int:
        counts = self.conditioned.get((phase, capability)) or self.phase_only.get(phase) or self.global_counts
        return max(counts, key=lambda target: (counts[target], -target))


def event_dict(view: Any, index: int, current_step: int) -> dict[str, Any]:
    return {
        "source_step": index + 1,
        "age": current_step - index - 1,
        "action": view.actions[index],
        "observation": view.observations[index],
        "capability": observable_capability(view.actions[index]),
    }


def payload(method: str, state: DelegationState, view: Any, step: int, phase: int, predicted_next_phase: int) -> dict[str, Any]:
    value: dict[str, Any] = {"current_delegation_state": state.to_dict()}
    if method == "M0_current_state":
        return value
    if method == "M1_state_task":
        value["task"] = view.task
    elif method == "M2_last_5_events":
        value["events"] = [event_dict(view, index, step) for index in range(max(0, step - 5), step)]
    elif method == "M3_full_trajectory":
        value["task"] = view.task
        value["events"] = [event_dict(view, index, step) for index in range(step)]
    elif method == "M4_dem":
        value["latent_phase"] = phase
        value["predicted_next_phase"] = predicted_next_phase
    else:
        raise ValueError(method)
    return value


def payload_tokens(value: dict[str, Any]) -> set[str]:
    tokens = {f"state:{dimension}={state_value}" for dimension, state_value in value["current_delegation_state"].items()}
    if "task" in value:
        tokens.update(f"task:{token}" for token in words(value["task"]))
    if "latent_phase" in value:
        tokens.add(f"phase:{value['latent_phase']}")
        tokens.add(f"next-phase:{value['predicted_next_phase']}")
    for event in value.get("events", []):
        tokens.add(f"age:{min(event['age'], 10)}")
        tokens.add(f"capability:{event['capability']}")
        tokens.update(f"action:{token}" for token in words(event["action"]))
        tokens.update(f"observation:{token}" for token in words(event["observation"]))
    return tokens


METHODS = ("M0_current_state", "M1_state_task", "M2_last_5_events", "M3_full_trajectory", "M4_dem")


def binary_f1(truth: list[bool], predicted: list[bool]) -> float:
    tp = sum(a and b for a, b in zip(truth, predicted))
    fp = sum(not a and b for a, b in zip(truth, predicted))
    fn = sum(a and not b for a, b in zip(truth, predicted))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0


def fit_phases(training: list[dict[str, Any]]) -> tuple[PhaseEncoder, PhaseTransitionModel]:
    vectors = []
    views = []
    for sample in training:
        view = sanitized_view(sample)
        views.append(view)
        vectors.extend(hashed_vector(view, step) for step in range(1, len(view.actions) + 1))
    encoder = PhaseEncoder()
    encoder.fit(vectors)
    sequences = []
    for view in views:
        phases = [encoder.encode(hashed_vector(view, step)) for step in range(1, len(view.actions) + 1)]
        capabilities = [observable_capability(action) for action in view.actions]
        sequences.append((phases, capabilities))
    transition_model = PhaseTransitionModel()
    transition_model.fit(sequences)
    return encoder, transition_model


def build_training_documents(
    training: list[dict[str, Any]], encoder: PhaseEncoder, phase_model: PhaseTransitionModel
) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    documents = {method: [] for method in METHODS}
    labels = []
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1, len(view.actions)):
            phase = encoder.encode(hashed_vector(view, step))
            next_phase = phase_model.predict(phase, observable_capability(view.actions[step - 1]))
            for method in METHODS:
                documents[method].append(payload_tokens(payload(method, oracle[step], view, step, phase, next_phase)))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def evaluate(
    evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval,
    encoder: PhaseEncoder, phase_model: PhaseTransitionModel,
    models: dict[str, MultiLabelModel],
) -> list[dict[str, Any]]:
    buckets = {
        (method, horizon): {"labels": [], "predictions": [], "sizes": [], "phase_correct": [], "phase_change_truth": [], "phase_change_prediction": []}
        for method in METHODS for horizon in HORIZONS
    }
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        phases = [encoder.encode(hashed_vector(view, step)) for step in range(1, len(view.actions) + 1)]
        predictions = {method: [] for method in METHODS}
        sizes = {method: [] for method in METHODS}
        predicted_phases = []
        for step in range(1, len(view.actions)):
            phase = phases[step - 1]
            next_phase = phase_model.predict(phase, observable_capability(view.actions[step - 1]))
            predicted_phases.append(next_phase)
            for method in METHODS:
                value = payload(method, inferred[step], view, step, phase, next_phase)
                predictions[method].append(models[method].predict(payload_tokens(value)))
                sizes[method].append(len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()))

        # No oracle is accessed until phases and all delegation deltas are fixed.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        labels = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        phase_correct = [predicted == actual for predicted, actual in zip(predicted_phases, phases[1:])]
        phase_change_truth = [current != future for current, future in zip(phases, phases[1:])]
        phase_change_prediction = [current != predicted for current, predicted in zip(phases, predicted_phases)]
        horizon = len(view.actions)
        for method in METHODS:
            bucket = buckets[(method, horizon)]
            bucket["labels"].extend(labels)
            bucket["predictions"].extend(predictions[method])
            bucket["sizes"].extend(sizes[method])
            bucket["phase_correct"].extend(phase_correct)
            bucket["phase_change_truth"].extend(phase_change_truth)
            bucket["phase_change_prediction"].extend(phase_change_prediction)

    rows = []
    for method in METHODS:
        for horizon in HORIZONS:
            data = buckets[(method, horizon)]
            rows.append({
                "method": method,
                "horizon": horizon,
                "delegation_state_recovery": "",  # filled below from shared inferred-state audit
                "transition_f1_macro": round(macro_f1(data["labels"], data["predictions"]), 4),
                "mean_serialized_context_bytes": round(mean(data["sizes"]), 1),
                "phase_consistency": round(mean(data["phase_correct"]), 4) if method == "M4_dem" else "",
                "phase_change_rate": round(mean(data["phase_change_truth"]), 4) if method == "M4_dem" else "",
                "phase_change_f1": round(binary_f1(data["phase_change_truth"], data["phase_change_prediction"]), 4) if method == "M4_dem" else "",
                "prediction_events": len(data["labels"]),
            })

    # Shared state inference is evaluated separately to avoid conflating memory.
    recovery: dict[int, list[bool]] = defaultdict(list)
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        recovery[len(view.actions)].extend(inferred[step] == oracle[step] for step in range(1, len(oracle)))
    for row in rows:
        row["delegation_state_recovery"] = round(mean(recovery[row["horizon"]]), 4)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1040, 570
    left, right, top, bottom = 75, 35, 55, 75
    panel_w = (width - left - right - 50) / 2
    plot_h = height - top - bottom
    colors = {"M0_current_state": "#64748b", "M1_state_task": "#f59e0b", "M2_last_5_events": "#8b5cf6", "M3_full_trajectory": "#059669", "M4_dem": "#2563eb"}
    max_size = max(float(row["mean_serialized_context_bytes"]) for row in rows)
    panels = (("transition_f1_macro", "Transition macro F1", 1.0), ("mean_serialized_context_bytes", "Serialized context bytes", max_size))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="520" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation Evolution Model by horizon</text>']
    for panel, (field, title, scale) in enumerate(panels):
        x0 = left + panel * (panel_w + 50)
        for tick in range(6):
            fraction = tick / 5; y = top + plot_h * (1 - fraction)
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_w}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            parts.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction*scale:.1f}</text>')
        parts.append(f'<text x="{x0+panel_w/2:.1f}" y="{top-12}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method, color in colors.items():
            points = []
            for index, horizon in enumerate(HORIZONS):
                row = next(value for value in rows if value["method"] == method and value["horizon"] == horizon)
                x = x0 + panel_w * index / (len(HORIZONS) - 1); y = top + plot_h * (1 - float(row[field]) / scale); points.append((x, y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            for x, y in points: parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        for index, horizon in enumerate(HORIZONS):
            x = x0 + panel_w * index / (len(HORIZONS) - 1); parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, (method, color) in enumerate(colors.items()):
        x = left + (index % 3) * 310; y = height - 35 + (index // 3) * 17
        parts.append(f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>'); parts.append(f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{method}</text>')
    parts.append("</svg>"); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/dem_results.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/dem_horizon.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    encoder, phase_model = fit_phases(training)
    documents, labels = build_training_documents(training, encoder, phase_model)
    models = {method: MultiLabelModel(documents[method], labels, "logistic") for method in METHODS}
    rows = evaluate(evaluation, state_model, encoder, phase_model, models)
    write_csv(args.output, rows); write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training), "evaluation_trajectories": len(evaluation),
        "latent_phases": PHASES, "results": rows,
        "phase_training": "unsupervised hashed-prefix k-means",
        "oracle_audit": "Phase fit uses no labels; evaluation labels are opened after all predictions.",
    }, indent=2))


if __name__ == "__main__":
    main()
