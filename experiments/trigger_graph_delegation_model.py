#!/usr/bin/env python3
"""Experiment 22: Trigger Dependency Graph delegation model.

At prefix t, the graph contains only triggers observed through t. It forecasts
both delta D_t and the trigger type at t+1. Future events and evaluation oracle
states are revealed only after a complete trajectory's predictions are fixed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
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
from trigger_delegation_model import TriggerState, boundary_events, capability_class, trigger_tokens


METHODS = ("M0_current_state", "M1_last_5_events", "M2_full_trajectory", "M3_flat_trigger", "M4_trigger_graph")
ATTRIBUTION_NONE = "none"


def event_triggers(previous_capability: str | None, previous_class: tuple[str, str] | None, action: str, observation: str) -> list[str]:
    """Observable trigger taxonomy; independent of delegation-state labels."""
    probe = TriggerState(previous_capability=previous_capability, previous_class=previous_class)
    before_observation = probe.observation_counts.copy()
    before_boundary = probe.boundary_counts.copy()
    probe.update(action, observation)
    found = [f"observation:{name}" for name in probe.observation_counts if probe.observation_counts[name] > before_observation[name]]
    found.extend(f"boundary:{name}" for name in probe.boundary_counts if probe.boundary_counts[name] > before_boundary[name])
    return sorted(found)


def canonical_trigger(triggers: list[str]) -> str:
    if not triggers:
        return ATTRIBUTION_NONE
    priority = ("reversible_to_irreversible", "internal_to_external", "write_to_execute", "read_to_write", "authentication", "approval", "error", "environment")
    return min(triggers, key=lambda value: next((index for index, key in enumerate(priority) if key in value), len(priority)))


@dataclass
class TriggerDependencyGraph:
    step: int = 0
    previous_capability: str | None = None
    previous_class: tuple[str, str] | None = None
    node_counts: Counter[str] = field(default_factory=Counter)
    edge_counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    last_seen: dict[str, int] = field(default_factory=dict)
    last_trigger: str | None = None

    def update(self, action: str, observation: str) -> list[str]:
        self.step += 1
        found = event_triggers(self.previous_capability, self.previous_class, action, observation)
        capability = observable_capability(action)
        current_class = capability_class(action, capability)
        for trigger in found:
            self.node_counts[trigger] += 1
            self.last_seen[trigger] = self.step
            if self.last_trigger is not None:
                self.edge_counts[(self.last_trigger, trigger)] += 1
            self.last_trigger = trigger
        self.previous_capability = capability
        self.previous_class = current_class
        return found

    def snapshot(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "last_trigger": self.last_trigger,
            "nodes": [
                {"type": node, "count": count, "recency": min(self.step - self.last_seen[node], 20)}
                for node, count in sorted(self.node_counts.items())
            ],
            "edges": [
                {"source": source, "target": target, "count": count}
                for (source, target), count in sorted(self.edge_counts.items())
            ],
        }


def graph_tokens(current: DelegationState, snapshot: dict[str, Any]) -> set[str]:
    tokens = {f"state:{dimension}={value}" for dimension, value in current.to_dict().items()}
    tokens.add(f"graph:step-bin={min(snapshot['step'], 20)}")
    tokens.add(f"graph:last={snapshot['last_trigger']}")
    for node in snapshot["nodes"]:
        tokens.add(f"graph:node={node['type']}")
        tokens.add(f"graph:node={node['type']}:count={min(node['count'], 5)}")
        tokens.add(f"graph:node={node['type']}:recency={min(node['recency'], 10)}")
    for edge in snapshot["edges"]:
        relation = f"{edge['source']}->{edge['target']}"
        tokens.add(f"graph:edge={relation}")
        tokens.add(f"graph:edge={relation}:count={min(edge['count'], 5)}")
    return tokens


def method_tokens(method: str, current: DelegationState, view: Any, step: int, flat: TriggerState, graph: TriggerDependencyGraph) -> set[str]:
    if method == "M0_current_state":
        return history_tokens(history_payload("M0_current_state", current, view, step, 0, 0))
    if method == "M1_last_5_events":
        return history_tokens(history_payload("M2_last_5_events", current, view, step, 0, 0))
    if method == "M2_full_trajectory":
        return history_tokens(history_payload("M3_full_trajectory", current, view, step, 0, 0))
    if method == "M3_flat_trigger":
        return trigger_tokens(current, flat.snapshot())
    if method == "M4_trigger_graph":
        return graph_tokens(current, graph.snapshot())
    raise ValueError(method)


def method_payload(method: str, current: DelegationState, view: Any, step: int, flat: TriggerState, graph: TriggerDependencyGraph) -> dict[str, Any]:
    if method == "M0_current_state":
        return history_payload("M0_current_state", current, view, step, 0, 0)
    if method == "M1_last_5_events":
        return history_payload("M2_last_5_events", current, view, step, 0, 0)
    if method == "M2_full_trajectory":
        return history_payload("M3_full_trajectory", current, view, step, 0, 0)
    if method == "M3_flat_trigger":
        return {"current_delegation_state": current.to_dict(), "trigger_state": flat.snapshot()}
    if method == "M4_trigger_graph":
        return {"current_delegation_state": current.to_dict(), "trigger_dependency_graph": graph.snapshot()}
    raise ValueError(method)


class AttributionModel:
    """Interpretable Bernoulli naive-Bayes trigger forecaster."""

    def __init__(self, documents: list[set[str]], labels: list[str]) -> None:
        self.classes = sorted(set(labels))
        self.class_counts = Counter(labels)
        self.token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.vocabulary = set().union(*documents)
        for document, label in zip(documents, labels):
            self.token_counts[label].update(document)

    def predict(self, document: set[str]) -> str:
        total = sum(self.class_counts.values())
        scores = {}
        for label in self.classes:
            class_count = self.class_counts[label]
            score = math.log((class_count + 1) / (total + len(self.classes)))
            for token in document & self.vocabulary:
                score += math.log((self.token_counts[label][token] + 1) / (class_count + 2))
            scores[label] = score
        return max(scores, key=lambda label: (scores[label], self.class_counts[label], label))


def build_training_data(training: list[dict[str, Any]]) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]], list[set[str]], list[str]]:
    documents = {method: [] for method in METHODS}
    transition_labels = []
    attribution_documents = []
    attribution_labels = []
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        flat, graph = TriggerState(), TriggerDependencyGraph()
        for step in range(1, len(view.actions)):
            flat.update(view.actions[step - 1], view.observations[step - 1])
            graph.update(view.actions[step - 1], view.observations[step - 1])
            for method in METHODS:
                documents[method].append(method_tokens(method, oracle[step], view, step, flat, graph))
            graph_document = graph_tokens(oracle[step], graph.snapshot())
            next_triggers = event_triggers(graph.previous_capability, graph.previous_class, view.actions[step], view.observations[step])
            attribution_documents.append(graph_document)
            attribution_labels.append(canonical_trigger(next_triggers))
            transition_labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, transition_labels, attribution_documents, attribution_labels


def evaluate(evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval, models: dict[str, MultiLabelModel], attribution_model: AttributionModel) -> list[dict[str, Any]]:
    buckets = defaultdict(lambda: {"truth": [], "predicted": [], "sizes": [], "attribution_truth": [], "attribution_predicted": [], "transition_count": 0, "covered_count": 0})
    for sample in evaluation:
        view = sanitized_view(sample)
        inferred = state_model.predict(view)
        flat, graph = TriggerState(), TriggerDependencyGraph()
        predictions = {method: [] for method in METHODS}
        sizes = {method: [] for method in METHODS}
        attribution_predictions = []
        for step in range(1, len(view.actions)):
            flat.update(view.actions[step - 1], view.observations[step - 1])
            graph.update(view.actions[step - 1], view.observations[step - 1])
            for method in METHODS:
                document = method_tokens(method, inferred[step], view, step, flat, graph)
                predictions[method].append(models[method].predict(document))
                payload = method_payload(method, inferred[step], view, step, flat, graph)
                sizes[method].append(len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()))
            attribution_predictions.append(attribution_model.predict(graph_tokens(inferred[step], graph.snapshot())))

        # Reveal all future events and oracle transitions only after prediction.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        actual_triggers = []
        audit_graph = TriggerDependencyGraph()
        for index in range(len(view.actions)):
            if index:
                actual_triggers.append(canonical_trigger(event_triggers(audit_graph.previous_capability, audit_graph.previous_class, view.actions[index], view.observations[index])))
            audit_graph.update(view.actions[index], view.observations[index])
        horizon = len(view.actions)
        for method in METHODS:
            bucket = buckets[(method, horizon)]
            bucket["truth"].extend(truth)
            bucket["predicted"].extend(predictions[method])
            bucket["sizes"].extend(sizes[method])
        graph_bucket = buckets[("M4_trigger_graph", horizon)]
        for label, actual, predicted in zip(truth, actual_triggers, attribution_predictions):
            if any(label):
                graph_bucket["transition_count"] += 1
                if actual != ATTRIBUTION_NONE:
                    graph_bucket["covered_count"] += 1
                    graph_bucket["attribution_truth"].append(actual)
                    graph_bucket["attribution_predicted"].append(predicted)

    rows = []
    for method in METHODS:
        for horizon in HORIZONS:
            data = buckets[(method, horizon)]
            correct = [truth == predicted for truth, predicted in zip(data["attribution_truth"], data["attribution_predicted"])]
            rows.append({
                "method": method,
                "horizon": horizon,
                "transition_f1_macro": round(macro_f1(data["truth"], data["predicted"]), 4),
                "trigger_attribution_accuracy": round(mean(correct), 4) if correct else "",
                "trigger_attribution_coverage": round(data["covered_count"] / data["transition_count"], 4) if data["transition_count"] else "",
                "mean_serialized_memory_bytes": round(mean(data["sizes"]), 1),
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
    width, height = 1040, 570
    left, top, bottom, gap, panel_width = 75, 55, 75, 55, 430
    plot_height = height - top - bottom
    colors = {"M0_current_state":"#64748b", "M1_last_5_events":"#8b5cf6", "M2_full_trajectory":"#059669", "M3_flat_trigger":"#f59e0b", "M4_trigger_graph":"#dc2626"}
    maximum = max(float(row["mean_serialized_memory_bytes"]) for row in rows)
    panels = (("transition_f1_macro", "Transition macro F1", 1.0), ("mean_serialized_memory_bytes", "Serialized memory bytes", maximum))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="520" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Trigger Dependency Graph by horizon</text>']
    for panel, (field, title, scale) in enumerate(panels):
        x0 = left + panel * (panel_width + gap)
        for tick in range(6):
            fraction = tick / 5; y = top + plot_height * (1 - fraction)
            parts += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_width}" y2="{y:.1f}" stroke="#e5e7eb"/>', f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction*scale:.1f}</text>']
        parts.append(f'<text x="{x0+panel_width/2}" y="{top-12}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
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
        x = 75 + (index % 3) * 300; y = height - 35 + (index // 3) * 17
        parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>', f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{method}</text>']
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/trigger_graph_model_results.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/trigger_graph_model_horizon.svg")
    args = parser.parse_args()
    training, evaluation = build_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    documents, labels, attribution_documents, attribution_labels = build_training_data(training)
    models = {method: MultiLabelModel(documents[method], labels, "logistic") for method in METHODS}
    attribution_model = AttributionModel(attribution_documents, attribution_labels)
    rows = evaluate(evaluation, state_model, models, attribution_model)
    write_csv(args.output, rows)
    write_svg(args.plot, rows)
    print(json.dumps({
        "training_trajectories": len(training), "evaluation_trajectories": len(evaluation), "results": rows,
        "attribution_definition": "Forecast next observable taxonomy trigger; accuracy is conditional on delegation transitions with a covered trigger.",
        "leakage_audit": "Graph updates use prefix events only; future triggers and oracle transitions open after predictions.",
    }, indent=2))


if __name__ == "__main__":
    main()
