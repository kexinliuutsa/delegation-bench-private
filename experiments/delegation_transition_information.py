#!/usr/bin/env python3
"""Experiment 17: information required for next delegation-transition prediction.

The target is binary: whether D_(t+1) differs from D_t. Training labels fit
nearest-neighbor predictors. At evaluation time, current states are inferred by
DEG and all predictions are completed before oracle states are opened.
"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from delegation_inference_baselines import (
    DelegationEvolutionGraph,
    Vectorizer,
    cosine,
    sanitized_view,
    training_examples,
)
from delegation_state_compression import HORIZONS, build_corpus
from models.delegation_state import DelegationState, state_transition


RECENT_WINDOW = 5


class BinaryTextPredictor:
    def __init__(self, examples: list[tuple[str, bool]]) -> None:
        self.vectorizer = Vectorizer(document for document, _ in examples)
        self.examples = [(self.vectorizer.transform(document), label) for document, label in examples]
        self.priors = Counter(label for _, label in examples)

    def predict(self, document: str) -> bool:
        vector = self.vectorizer.transform(document)
        _, label = max(
            self.examples,
            key=lambda item: (cosine(vector, item[0]), self.priors[item[1]], item[1]),
        )
        return label


def events(view: Any, start: int, stop: int) -> list[dict[str, str]]:
    return [
        {"action": action, "observation": observation}
        for action, observation in zip(view.actions[start:stop], view.observations[start:stop])
    ]


def payload_m0(state: DelegationState, view: Any, step: int) -> dict[str, Any]:
    del view, step
    return {"current_delegation_state": state.to_dict()}


def payload_m1(state: DelegationState, view: Any, step: int) -> dict[str, Any]:
    del step
    return {"current_delegation_state": state.to_dict(), "task": view.task}


def payload_m2(state: DelegationState, view: Any, step: int) -> dict[str, Any]:
    start = max(0, step - RECENT_WINDOW)
    return {
        "current_delegation_state": state.to_dict(),
        "recent_history": events(view, start, step),
    }


def payload_m3(state: DelegationState, view: Any, step: int) -> dict[str, Any]:
    del state
    return {"task": view.task, "complete_history": events(view, 0, step)}


PAYLOADS: dict[str, Callable[[DelegationState, Any, int], dict[str, Any]]] = {
    "M0_current_state": payload_m0,
    "M1_state_task": payload_m1,
    "M2_state_recent_history": payload_m2,
    "M3_full_trajectory": payload_m3,
}


def serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def build_training_examples(training: list[dict[str, Any]]) -> dict[str, list[tuple[str, bool]]]:
    output = {method: [] for method in PAYLOADS}
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1, len(view.actions)):
            label = bool(state_transition(oracle[step], oracle[step + 1])["changed"])
            for method, payload in PAYLOADS.items():
                output[method].append((serialize(payload(oracle[step], view, step)), label))
    return output


def binary_f1(truth: list[bool], predicted: list[bool]) -> float:
    tp = sum(a and b for a, b in zip(truth, predicted))
    fp = sum(not a and b for a, b in zip(truth, predicted))
    fn = sum(a and not b for a, b in zip(truth, predicted))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0


def evaluate(
    evaluation: list[dict[str, Any]],
    deg: DelegationEvolutionGraph,
    predictors: dict[str, BinaryTextPredictor],
) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, int], dict[str, list[Any]]] = {
        (method, horizon): {"truth": [], "prediction": [], "size": []}
        for method in PAYLOADS for horizon in HORIZONS
    }
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred_states = deg.predict(view)
        predictions: dict[str, list[bool]] = {method: [] for method in PAYLOADS}
        sizes: dict[str, list[int]] = {method: [] for method in PAYLOADS}
        for step in range(1, len(view.actions)):
            for method, payload_function in PAYLOADS.items():
                document = serialize(payload_function(inferred_states[step], view, step))
                predictions[method].append(predictors[method].predict(document))
                sizes[method].append(len(document.encode()))

        # Evaluation oracle is opened only after every representation predicts.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [
            bool(state_transition(oracle[step], oracle[step + 1])["changed"])
            for step in range(1, len(view.actions))
        ]
        horizon = len(view.actions)
        for method in PAYLOADS:
            bucket = buckets[(method, horizon)]
            bucket["truth"].extend(truth)
            bucket["prediction"].extend(predictions[method])
            bucket["size"].extend(sizes[method])

    rows = []
    for method in PAYLOADS:
        for horizon in HORIZONS:
            data = buckets[(method, horizon)]
            rows.append({
                "method": method,
                "horizon": horizon,
                "transition_f1": round(binary_f1(data["truth"], data["prediction"]), 4),
                "transition_accuracy": round(mean(a == b for a, b in zip(data["truth"], data["prediction"])), 4),
                "mean_serialized_input_bytes": round(mean(data["size"]), 1),
                "final_serialized_input_bytes": max(data["size"]),
                "prediction_events": len(data["truth"]),
                "positive_transitions": sum(data["truth"]),
            })
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
    colors = {
        "M0_current_state": "#64748b",
        "M1_state_task": "#f59e0b",
        "M2_state_recent_history": "#8b5cf6",
        "M3_full_trajectory": "#2563eb",
    }
    max_size = max(float(row["mean_serialized_input_bytes"]) for row in rows)
    panels = (("transition_f1", "Next-transition F1", 1.0), ("mean_serialized_input_bytes", "Mean serialized bytes", max_size))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="520" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Information for next delegation-transition prediction</text>',
    ]
    for panel, (field, title, scale) in enumerate(panels):
        x0 = left + panel * (panel_w + 50)
        for tick in range(6):
            fraction = tick / 5
            y = top + plot_h * (1 - fraction)
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_w}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            parts.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction*scale:.1f}</text>')
        parts.append(f'<text x="{x0+panel_w/2:.1f}" y="{top-12}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method, color in colors.items():
            points = []
            for index, horizon in enumerate(HORIZONS):
                row = next(value for value in rows if value["method"] == method and value["horizon"] == horizon)
                x = x0 + panel_w * index / (len(HORIZONS) - 1)
                y = top + plot_h * (1 - float(row[field]) / scale)
                points.append((x, y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            for x, y in points:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        for index, horizon in enumerate(HORIZONS):
            x = x0 + panel_w * index / (len(HORIZONS) - 1)
            parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, (method, color) in enumerate(colors.items()):
        x = left + index * 235
        parts.append(f'<rect x="{x}" y="{height-28}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{x+17}" y="{height-18}" font-family="sans-serif" font-size="10">{method}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/delegation_transition_information.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/delegation_transition_information.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    graph_examples = training_examples(training)[3]
    deg = DelegationEvolutionGraph(graph_examples)
    examples = build_training_examples(training)
    predictors = {method: BinaryTextPredictor(values) for method, values in examples.items()}
    rows = evaluate(evaluation, deg, predictors)
    write_csv(args.output, rows)
    write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training),
        "evaluation_trajectories": len(evaluation),
        "recent_history_window": RECENT_WINDOW,
        "results": rows,
        "target": "binary D_(t+1) != D_t",
        "oracle_isolation": "DEG states and transition predictions are complete before evaluation labels are opened.",
    }, indent=2))


if __name__ == "__main__":
    main()
