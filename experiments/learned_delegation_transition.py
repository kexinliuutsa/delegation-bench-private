#!/usr/bin/env python3
"""Experiment 18: learned multilabel delegation-transition prediction.

Each target bit indicates whether one delegation dimension changes at t+1.
Current D_t is inferred from the observable prefix by a learned state retriever.
No feature builder or predictor receives future events or evaluation oracle data.

The environment lacks scikit-learn/XGBoost, so this file provides deterministic
weighted sparse logistic regression and balanced-bootstrap random forests.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from delegation_inference_baselines import FullHistoryRetrieval, observable_capability, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from models.delegation_state import DelegationState, VALUE_ORDERS


DIMENSIONS = tuple(VALUE_ORDERS)
RECENT_WINDOW = 5


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def payload(method: str, state: DelegationState, view: Any, step: int) -> dict[str, Any]:
    value: dict[str, Any] = {"current_state": state.to_dict()}
    if method in {"M1_state_task_logistic", "M3_full_logistic", "M3_full_random_forest"}:
        value["task"] = view.task
    if method in {"M2_state_recent_logistic", "M3_full_logistic", "M3_full_random_forest"}:
        start = max(0, step - RECENT_WINDOW)
        value["recent_events"] = [
            {"action": action, "observation": observation}
            for action, observation in zip(view.actions[start:step], view.observations[start:step])
        ]
    if method in {"M3_full_logistic", "M3_full_random_forest"}:
        start = max(0, step - RECENT_WINDOW)
        value["capability_sequence"] = [observable_capability(action) for action in view.actions[start:step]]
    return value


def payload_tokens(value: dict[str, Any]) -> set[str]:
    tokens = {f"state:{dimension}={state_value}" for dimension, state_value in value["current_state"].items()}
    if "task" in value:
        tokens.update(f"task:{token}" for token in words(value["task"]))
    events = value.get("recent_events", [])
    for offset, event in enumerate(reversed(events), start=1):
        tokens.update(f"action-{offset}:{token}" for token in words(event["action"]))
        tokens.update(f"observation-{offset}:{token}" for token in words(event["observation"]))
    for offset, capability in enumerate(reversed(value.get("capability_sequence", [])), start=1):
        tokens.add(f"capability-{offset}:{capability}")
    return tokens


class Vocabulary:
    def __init__(self, documents: list[set[str]]) -> None:
        frequencies = Counter(token for document in documents for token in document)
        self.indices = {token: index for index, (token, _) in enumerate(sorted(frequencies.items(), key=lambda item: (-item[1], item[0])))}

    def transform(self, document: set[str]) -> set[int]:
        return {self.indices[token] for token in document if token in self.indices}


class WeightedLogistic:
    def __init__(self, feature_count: int, epochs: int = 32, learning_rate: float = 0.08, l2: float = 1e-4) -> None:
        self.weights = [0.0] * feature_count
        self.bias = 0.0
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.l2 = l2

    @staticmethod
    def sigmoid(value: float) -> float:
        value = max(-30.0, min(30.0, value))
        return 1.0 / (1.0 + math.exp(-value))

    def fit(self, features: list[set[int]], labels: list[int]) -> None:
        positives = sum(labels)
        positive_weight = (len(labels) - positives) / positives if positives else 1.0
        order = list(range(len(labels)))
        for epoch in range(self.epochs):
            rate = self.learning_rate / math.sqrt(epoch + 1)
            random.Random(1701 + epoch).shuffle(order)
            for index in order:
                active = features[index]
                probability = self.sigmoid(self.bias + sum(self.weights[item] for item in active))
                sample_weight = positive_weight if labels[index] else 1.0
                gradient = (probability - labels[index]) * sample_weight
                self.bias -= rate * gradient
                for item in active:
                    self.weights[item] -= rate * (gradient + self.l2 * self.weights[item])

    def predict(self, features: set[int]) -> int:
        return int(self.sigmoid(self.bias + sum(self.weights[item] for item in features)) >= 0.5)


@dataclass
class TreeNode:
    probability: float
    feature: int | None = None
    absent: "TreeNode | None" = None
    present: "TreeNode | None" = None


class BinaryTree:
    def __init__(self, feature_count: int, seed: int, max_depth: int = 6, min_samples: int = 10) -> None:
        self.feature_count = feature_count
        self.random = random.Random(seed)
        self.max_depth = max_depth
        self.min_samples = min_samples
        self.root: TreeNode | None = None

    @staticmethod
    def gini(labels: list[int]) -> float:
        if not labels:
            return 0.0
        probability = sum(labels) / len(labels)
        return 2 * probability * (1 - probability)

    def build(self, features: list[set[int]], labels: list[int], indices: list[int], depth: int) -> TreeNode:
        node_labels = [labels[index] for index in indices]
        probability = sum(node_labels) / len(node_labels)
        if depth >= self.max_depth or len(indices) < self.min_samples or probability in {0.0, 1.0}:
            return TreeNode(probability)
        candidate_count = max(5, int(math.sqrt(self.feature_count)))
        candidates = self.random.sample(range(self.feature_count), min(candidate_count, self.feature_count))
        base = self.gini(node_labels)
        best: tuple[float, int, list[int], list[int]] | None = None
        for candidate in candidates:
            present = [index for index in indices if candidate in features[index]]
            absent = [index for index in indices if candidate not in features[index]]
            if not present or not absent:
                continue
            impurity = (len(present) * self.gini([labels[i] for i in present]) + len(absent) * self.gini([labels[i] for i in absent])) / len(indices)
            gain = base - impurity
            if best is None or gain > best[0]:
                best = (gain, candidate, absent, present)
        if best is None or best[0] <= 0:
            return TreeNode(probability)
        _, candidate, absent, present = best
        return TreeNode(probability, candidate, self.build(features, labels, absent, depth + 1), self.build(features, labels, present, depth + 1))

    def fit(self, features: list[set[int]], labels: list[int]) -> None:
        positive = [index for index, label in enumerate(labels) if label]
        negative = [index for index, label in enumerate(labels) if not label]
        count = max(len(positive), min(len(negative), len(positive) * 3))
        bootstrap = [self.random.choice(positive) for _ in range(count)] + [self.random.choice(negative) for _ in range(count)]
        self.random.shuffle(bootstrap)
        self.root = self.build(features, labels, bootstrap, 0)

    def probability(self, features: set[int]) -> float:
        if self.root is None:
            raise RuntimeError("tree not fitted")
        node = self.root
        while node.feature is not None:
            node = node.present if node.feature in features else node.absent  # type: ignore[assignment]
        return node.probability


class RandomForest:
    def __init__(self, feature_count: int, trees: int = 9, seed: int = 911) -> None:
        self.trees = [BinaryTree(feature_count, seed + index) for index in range(trees)]

    def fit(self, features: list[set[int]], labels: list[int]) -> None:
        for tree in self.trees:
            tree.fit(features, labels)

    def predict(self, features: set[int]) -> int:
        return int(mean(tree.probability(features) for tree in self.trees) >= 0.5)


class MultiLabelModel:
    def __init__(self, documents: list[set[str]], labels: list[tuple[int, ...]], family: str) -> None:
        self.vocabulary = Vocabulary(documents)
        transformed = [self.vocabulary.transform(document) for document in documents]
        self.models = []
        for dimension_index in range(len(DIMENSIONS)):
            targets = [label[dimension_index] for label in labels]
            model: Any
            if family == "logistic":
                model = WeightedLogistic(len(self.vocabulary.indices))
            elif family == "random_forest":
                model = RandomForest(len(self.vocabulary.indices), seed=911 + dimension_index * 101)
            else:
                raise ValueError(family)
            model.fit(transformed, targets)
            self.models.append(model)

    def predict(self, document: set[str]) -> tuple[int, ...]:
        features = self.vocabulary.transform(document)
        return tuple(model.predict(features) for model in self.models)


def delta_label(current: DelegationState, future: DelegationState) -> tuple[int, ...]:
    return tuple(int(getattr(current, dimension) != getattr(future, dimension)) for dimension in DIMENSIONS)


def build_examples(training: list[dict[str, Any]], state_model: FullHistoryRetrieval, method: str) -> tuple[list[set[str]], list[tuple[int, ...]]]:
    documents = []
    labels = []
    for sample in training:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1, len(view.actions)):
            documents.append(payload_tokens(payload(method, inferred[step], view, step)))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def build_all_examples(
    training: list[dict[str, Any]],
    methods: tuple[str, ...],
) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    """Use supervised training D_t, then construct every feature ablation."""
    documents = {method: [] for method in methods}
    labels: list[tuple[int, ...]] = []
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1, len(view.actions)):
            for method in methods:
                documents[method].append(payload_tokens(payload(method, oracle[step], view, step)))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def macro_f1(labels: list[tuple[int, ...]], predictions: list[tuple[int, ...]]) -> float:
    scores = []
    for index in range(len(DIMENSIONS)):
        truth = [value[index] for value in labels]
        predicted = [value[index] for value in predictions]
        tp = sum(a and b for a, b in zip(truth, predicted))
        fp = sum(not a and b for a, b in zip(truth, predicted))
        fn = sum(a and not b for a, b in zip(truth, predicted))
        scores.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0)
    return mean(scores)


def evaluate(evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval, models: dict[str, MultiLabelModel]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, list[Any]]] = {
        (method, horizon): {"labels": [], "predictions": [], "sizes": []}
        for method in models for horizon in ("overall", "5", "10", "20", "50")
    }
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        all_predictions: dict[str, list[tuple[int, ...]]] = {method: [] for method in models}
        all_sizes: dict[str, list[int]] = {method: [] for method in models}
        for step in range(1, len(view.actions)):
            for method, model in models.items():
                value = payload(method, inferred[step], view, step)
                all_predictions[method].append(model.predict(payload_tokens(value)))
                all_sizes[method].append(len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()))

        # Future oracle states are opened only after every model predicts.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        labels = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        horizon = str(len(view.actions))
        for method in models:
            for bucket_name in ("overall", horizon):
                bucket = buckets[(method, bucket_name)]
                bucket["labels"].extend(labels)
                bucket["predictions"].extend(all_predictions[method])
                bucket["sizes"].extend(all_sizes[method])

    rows = []
    for method in models:
        for horizon in ("overall", "5", "10", "20", "50"):
            data = buckets[(method, horizon)]
            row: dict[str, Any] = {
                "method": method,
                "model_family": "random_forest" if method.endswith("random_forest") else "logistic_regression",
                "horizon": horizon,
                "transition_f1_macro": round(macro_f1(data["labels"], data["predictions"]), 4),
            }
            for index, dimension in enumerate(DIMENSIONS):
                row[f"{dimension}_transition_accuracy"] = round(mean(label[index] == prediction[index] for label, prediction in zip(data["labels"], data["predictions"])), 4)
            row["mean_serialized_input_bytes"] = round(mean(data["sizes"]), 1)
            row["prediction_events"] = len(data["labels"])
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1020, 560
    left, right, top, bottom = 75, 35, 55, 80
    plot_w, plot_h = width - left - right, height - top - bottom
    methods = list(dict.fromkeys(row["method"] for row in rows))
    colors = ("#64748b", "#f59e0b", "#8b5cf6", "#2563eb", "#059669")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="510" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Learned delegation transition prediction by horizon</text>',
    ]
    for tick in range(6):
        value = tick / 5
        y = top + plot_h * (1 - value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>')
    horizons = (5, 10, 20, 50)
    for method, color in zip(methods, colors):
        points = []
        for index, horizon in enumerate(horizons):
            row = next(value for value in rows if value["method"] == method and value["horizon"] == str(horizon))
            x = left + plot_w * index / (len(horizons) - 1)
            y = top + plot_h * (1 - float(row["transition_f1_macro"]))
            points.append((x, y))
        parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x, y in points:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
    for index, horizon in enumerate(horizons):
        x = left + plot_w * index / (len(horizons) - 1)
        parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, (method, color) in enumerate(zip(methods, colors)):
        x = left + (index % 3) * 310
        y = height - 35 + (index // 3) * 18
        parts.append(f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{method}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/learned_transition_results.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/learned_transition_horizon.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    methods = (
        "M0_current_state_logistic",
        "M1_state_task_logistic",
        "M2_state_recent_logistic",
        "M3_full_logistic",
        "M3_full_random_forest",
    )
    documents_by_method, labels = build_all_examples(training, methods)
    models = {}
    for method in methods:
        family = "random_forest" if method.endswith("random_forest") else "logistic"
        models[method] = MultiLabelModel(documents_by_method[method], labels, family)
    rows = evaluate(evaluation, state_model, models)
    write_csv(args.output, rows)
    write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training),
        "evaluation_trajectories": len(evaluation),
        "recent_window": RECENT_WINDOW,
        "overall_results": [row for row in rows if row["horizon"] == "overall"],
        "xgboost": "unavailable (package not installed)",
        "target_dimensions": DIMENSIONS,
        "oracle_isolation": "Current state is learned from the prefix; future labels are opened only after predictions.",
    }, indent=2))


if __name__ == "__main__":
    main()
