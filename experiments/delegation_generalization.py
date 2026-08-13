#!/usr/bin/env python3
"""Experiment 25: CDEM generalization and stage-token stress tests.

Anonymous and permuted stage identifiers are inferred online from repeated
observable action strings. No generator stage metadata enters a predictor.
Evaluation oracle transitions are opened only after all predictions are fixed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from context_delegation_evolution import ExecutionContextState, context_tokens
from delegation_evolution_model import payload as history_payload, payload_tokens as history_tokens
from delegation_inference_baselines import FullHistoryRetrieval, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from delegationbench_compositional_split import TEST_STAGES, TRAIN_STAGES, make_sample
from learned_delegation_transition import MultiLabelModel, delta_label, macro_f1
from models.delegation_state import DelegationState
from trigger_delegation_model import TriggerState, trigger_tokens


METHODS = ("M0_state_only", "M1_trigger", "M2_full_history", "M3_cdem")
STAGE_VARIANTS = ("original", "anonymous", "permuted")


class OnlineStageEncoder:
    """Derive stage IDs using prefix-only action identity."""

    def __init__(self, variant: str, sample_id: str) -> None:
        self.variant = variant
        self.mapping: dict[str, str] = {}
        seed = int.from_bytes(hashlib.blake2b(sample_id.encode(), digest_size=8).digest(), "big")
        self.permutation = list(range(32))
        random.Random(seed).shuffle(self.permutation)

    def encode(self, action: str) -> str:
        if self.variant == "original":
            return "_".join(part for part in action.lower().split() if part)
        if action not in self.mapping:
            ordinal = len(self.mapping)
            phase = ordinal if self.variant == "anonymous" else self.permutation[ordinal]
            self.mapping[action] = f"phase_{phase}"
        return self.mapping[action]


def cdem_variant_tokens(current: DelegationState, flat: TriggerState, context: ExecutionContextState, stage_id: str) -> set[str]:
    tokens = context_tokens(current, flat, context)
    tokens = {token for token in tokens if not token.startswith("context:stage=")}
    tokens.add(f"context:stage={stage_id}")
    return tokens


def method_features(method: str, current: DelegationState, view: Any, step: int, flat: TriggerState, context: ExecutionContextState, stage_id: str) -> set[str]:
    if method == "M0_state_only":
        return history_tokens(history_payload("M0_current_state", current, view, step, 0, 0))
    if method == "M1_trigger":
        return trigger_tokens(current, flat.snapshot())
    if method == "M2_full_history":
        return history_tokens(history_payload("M3_full_trajectory", current, view, step, 0, 0))
    if method == "M3_cdem":
        return cdem_variant_tokens(current, flat, context, stage_id)
    raise ValueError(method)


def build_training_documents(training: list[dict[str, Any]], variant: str) -> tuple[dict[str, list[set[str]]], list[tuple[int, ...]]]:
    documents = {method: [] for method in METHODS}; labels = []
    for sample in training:
        view = sanitized_view(sample); oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        flat, context, stage = TriggerState(), ExecutionContextState(view.task), OnlineStageEncoder(variant, view.sample_id)
        for step in range(1, len(view.actions)):
            action, observation = view.actions[step - 1], view.observations[step - 1]
            flat.update(action, observation); context.update(action, observation); stage_id = stage.encode(action)
            for method in METHODS:
                documents[method].append(method_features(method, oracle[step], view, step, flat, context, stage_id))
            labels.append(delta_label(oracle[step], oracle[step + 1]))
    return documents, labels


def evaluate_variant(evaluation: list[dict[str, Any]], state_model: FullHistoryRetrieval, models: dict[str, MultiLabelModel], variant: str, experiment: str) -> list[dict[str, Any]]:
    buckets = defaultdict(lambda: {"truth": [], "predicted": []})
    for sample in evaluation:
        view = sanitized_view(sample); inferred = state_model.predict(view)
        flat, context, stage = TriggerState(), ExecutionContextState(view.task), OnlineStageEncoder(variant, view.sample_id)
        predictions = {method: [] for method in METHODS}
        for step in range(1, len(view.actions)):
            action, observation = view.actions[step - 1], view.observations[step - 1]
            flat.update(action, observation); context.update(action, observation); stage_id = stage.encode(action)
            for method in METHODS:
                predictions[method].append(models[method].predict(method_features(method, inferred[step], view, step, flat, context, stage_id)))
        # No evaluation label is available before the complete prediction pass.
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        truth = [delta_label(oracle[step], oracle[step + 1]) for step in range(1, len(view.actions))]
        horizon = len(view.actions)
        for method in METHODS:
            buckets[(method, horizon)]["truth"].extend(truth); buckets[(method, horizon)]["predicted"].extend(predictions[method])
    return [{
        "experiment": experiment,
        "stage_representation": variant if method == "M3_cdem" else "not_applicable",
        "method": method,
        "horizon": horizon,
        "transition_f1_macro": round(macro_f1(buckets[(method, horizon)]["truth"], buckets[(method, horizon)]["predicted"]), 4),
        "stage_anonymization_drop_percent": "",
        "prediction_events": len(buckets[(method, horizon)]["truth"]),
    } for method in METHODS for horizon in HORIZONS]


def controlled_stage_experiments() -> list[dict[str, Any]]:
    training, evaluation = build_corpus(); rows = []
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    for variant in STAGE_VARIANTS:
        documents, labels = build_training_documents(training, variant)
        models = {method: MultiLabelModel(documents[method], labels, "logistic") for method in METHODS}
        variant_rows = evaluate_variant(evaluation, state_model, models, variant, f"stage_{variant}")
        rows.extend(row for row in variant_rows if row["method"] == "M3_cdem" or variant == "original")
    originals = {int(row["horizon"]): row for row in rows if row["experiment"] == "stage_original" and row["method"] == "M3_cdem"}
    for row in rows:
        if row["experiment"] == "stage_anonymous" and row["method"] == "M3_cdem":
            baseline = float(originals[int(row["horizon"])]["transition_f1_macro"])
            row["stage_anonymization_drop_percent"] = round(100 * (baseline - float(row["transition_f1_macro"])) / baseline, 2) if baseline else ""
    return rows


def hard_split_corpus() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    names = {5: "short", 10: "medium", 20: "long", 50: "fifty"}; training = []; evaluation = []; index = 5000
    for split_name, groups, replicates in (("train", TRAIN_STAGES, 5), ("test", TEST_STAGES, 2)):
        for category, stages in groups.items():
            for horizon in HORIZONS:
                for _ in range(replicates):
                    index += 1
                    sample = make_sample(split_name, category, stages, names[horizon], horizon, index)
                    (training if split_name == "train" else evaluation).append(sample)
    return training, evaluation


def domain_experiment() -> list[dict[str, Any]]:
    training, evaluation = hard_split_corpus()
    state_model = FullHistoryRetrieval(training_examples(training)[2])
    documents, labels = build_training_documents(training, "original")
    models = {method: MultiLabelModel(documents[method], labels, "logistic") for method in METHODS}
    return evaluate_variant(evaluation, state_model, models, "original", "domain_compositional_split")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1100, 610; left, top, bottom, gap, panel_width = 75, 60, 80, 60, 455; plot_height = height - top - bottom
    panels = (("stage", "CDEM stage stress tests"), ("domain", "Domain compositional split"))
    styles = {
        "stage_original:M3_cdem": ("#111827", "CDEM original"), "stage_anonymous:M3_cdem": ("#dc2626", "CDEM anonymous"), "stage_permuted:M3_cdem": ("#f59e0b", "CDEM permuted"),
        "domain_compositional_split:M0_state_only": ("#64748b", "state only"), "domain_compositional_split:M1_trigger": ("#f59e0b", "trigger"), "domain_compositional_split:M2_full_history": ("#059669", "full history"), "domain_compositional_split:M3_cdem": ("#dc2626", "CDEM"),
    }
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="550" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation evolution generalization</text>']
    legend_items = []
    for panel_index, (kind, title) in enumerate(panels):
        x0 = left + panel_index * (panel_width + gap)
        for tick in range(6):
            fraction = tick / 5; y = top + plot_height * (1 - fraction)
            parts += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_width}" y2="{y:.1f}" stroke="#e5e7eb"/>', f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction:.1f}</text>']
        parts.append(f'<text x="{x0+panel_width/2}" y="{top-13}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        selected = {key: value for key, value in styles.items() if (kind == "stage" and key.startswith("stage_")) or (kind == "domain" and key.startswith("domain_"))}
        for key, (color, label) in selected.items():
            experiment, method = key.split(":")
            points = []
            for index, horizon in enumerate(HORIZONS):
                row = next(item for item in rows if item["experiment"] == experiment and item["method"] == method and int(item["horizon"]) == horizon)
                x = x0 + panel_width * index / (len(HORIZONS) - 1); y = top + plot_height * (1 - float(row["transition_f1_macro"])); points.append((x, y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>' for x, y in points)
            legend_items.append((color, f"{kind}: {label}"))
        for index, horizon in enumerate(HORIZONS):
            x = x0 + panel_width * index / (len(HORIZONS) - 1); parts.append(f'<text x="{x:.1f}" y="{top+plot_height+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index, (color, label) in enumerate(legend_items):
        x = 70 + (index % 4) * 260; y = height - 42 + (index // 4) * 16
        parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>', f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="9">{label}</text>']
    parts.append("</svg>"); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/delegation_generalization.csv")
    parser.add_argument("--plot", type=Path, default=ROOT / "results/delegation_generalization.svg")
    args = parser.parse_args()
    stage_rows = controlled_stage_experiments(); domain_rows = domain_experiment(); rows = stage_rows + domain_rows
    write_csv(args.output, rows); write_svg(args.plot, rows)
    print(json.dumps({
        "results": rows,
        "domain_train": list(TRAIN_STAGES), "domain_test": list(TEST_STAGES),
        "stage_id_audit": "Anonymous/permuted IDs are online encodings of observed action equality; generator stage IDs are never read.",
        "leakage_audit": "Predictors use task and observable prefix only; evaluation oracles open after prediction.",
    }, indent=2))


if __name__ == "__main__":
    main()
