#!/usr/bin/env python3
"""Diagnose trajectory-level aggregation of three-fold OOF anomaly scores."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.cross_domain_monitor_transfer import auroc


def percentile_value(values: list[float], q: float) -> float:
    values = sorted(values)
    index = (len(values) - 1) * q
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - index) + values[upper] * (index - lower)


def aggregate(values: list[float], method: str) -> float:
    ordered = sorted(values, reverse=True)
    if method == "max":
        return ordered[0]
    if method == "mean":
        return mean(ordered)
    if method == "top2_mean":
        return mean(ordered[: min(2, len(ordered))])
    if method == "top3_mean":
        return mean(ordered[: min(3, len(ordered))])
    if method == "q90":
        ascending = list(reversed(ordered))
        index = .9 * (len(ascending) - 1)
        lower, upper = math.floor(index), math.ceil(index)
        return ascending[lower] if lower == upper else (
            ascending[lower] * (upper - index) + ascending[upper] * (index - lower)
        )
    raise ValueError(method)


def bootstrap_auc(rows: list[dict], method: str, resamples: int = 10000) -> tuple[float, float]:
    rng = random.Random(67001)
    values = []
    for _ in range(resamples):
        sample = [rng.choice(rows) for _ in rows]
        controls = [aggregate(row["control_scores"], method) for row in sample]
        treatments = [aggregate(row["treatment_scores"], method) for row in sample]
        values.append(auroc([False] * len(sample) + [True] * len(sample), controls + treatments))
    return percentile_value(values, .025), percentile_value(values, .975)


def rank_correlation(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=values.__getitem__)
        result = [0.0] * len(values)
        for rank, index in enumerate(order):
            result[index] = rank
        return result
    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    numerator = sum((x - mx) * (y - my) for x, y in zip(rx, ry))
    denominator = math.sqrt(sum((x - mx) ** 2 for x in rx) * sum((y - my) ** 2 for y in ry))
    return numerator / denominator if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    base = ROOT / "results/multi_agent_delegation/pibr_oof_threshold_diagnostics"
    parser.add_argument("--scores", type=Path, default=base / "oof_trajectory_scores.jsonl")
    parser.add_argument("--output-dir", type=Path, default=base / "pair_aggregation")
    parser.add_argument("--resamples", type=int, default=10000)
    args = parser.parse_args()
    rows_by_representation: dict[str, list[dict]] = {}
    for line in args.scores.read_text().splitlines():
        row = json.loads(line)
        rows_by_representation.setdefault(row.pop("representation"), []).append(row)

    methods = ("max", "top2_mean", "top3_mean", "q90", "mean")
    results = []
    per_fold_results = []
    diagnostics = []
    for representation, rows in rows_by_representation.items():
        for method in methods:
            controls = [aggregate(row["control_scores"], method) for row in rows]
            treatments = [aggregate(row["treatment_scores"], method) for row in rows]
            low, high = bootstrap_auc(rows, method, args.resamples)
            deltas = [treatment - control for control, treatment in zip(controls, treatments)]
            results.append({
                "representation": representation,
                "aggregation": method,
                "trajectory_auroc_control_vs_treatment": round(
                    auroc([False] * len(rows) + [True] * len(rows), controls + treatments), 4
                ),
                "pair_cluster_bootstrap_low": round(low, 4),
                "pair_cluster_bootstrap_high": round(high, 4),
                "mean_control": round(mean(controls), 6),
                "mean_treatment": round(mean(treatments), 6),
                "mean_paired_delta": round(mean(deltas), 6),
                "pairs_treatment_above_control": sum(delta > 0 for delta in deltas),
                "pairs": len(rows),
            })
            for fold in (0, 1, 2):
                fold_rows = [row for row in rows if row["fold"] == fold]
                fold_controls = [aggregate(row["control_scores"], method) for row in fold_rows]
                fold_treatments = [aggregate(row["treatment_scores"], method) for row in fold_rows]
                per_fold_results.append({
                    "representation": representation,
                    "aggregation": method,
                    "heldout_seed": fold,
                    "pairs": len(fold_rows),
                    "trajectory_auroc_control_vs_treatment": round(
                        auroc(
                            [False] * len(fold_rows) + [True] * len(fold_rows),
                            fold_controls + fold_treatments,
                        ),
                        4,
                    ),
                    "pairs_treatment_above_control": sum(
                        treatment > control
                        for control, treatment in zip(fold_controls, fold_treatments)
                    ),
                })

        control_lengths = [len(row["control_scores"]) for row in rows]
        treatment_lengths = [len(row["treatment_scores"]) for row in rows]
        control_maxima = [max(row["control_scores"]) for row in rows]
        treatment_maxima = [max(row["treatment_scores"]) for row in rows]
        changed_scores = [
            score
            for row in rows
            for step, score in enumerate(row["treatment_scores"], 1)
            if step in row["changed_steps"]
        ]
        unchanged_treatment_scores = [
            score
            for row in rows
            for step, score in enumerate(row["treatment_scores"], 1)
            if step not in row["changed_steps"]
        ]
        diagnostics.append({
            "representation": representation,
            "control_length_mean": round(mean(control_lengths), 4),
            "treatment_length_mean": round(mean(treatment_lengths), 4),
            "spearman_control_length_vs_max": round(rank_correlation(control_lengths, control_maxima), 4),
            "spearman_treatment_length_vs_max": round(rank_correlation(treatment_lengths, treatment_maxima), 4),
            "mean_changed_step_score": round(mean(changed_scores), 6),
            "mean_unchanged_treatment_step_score": round(mean(unchanged_treatment_scores), 6),
            "changed_vs_unchanged_step_auroc": round(
                auroc(
                    [True] * len(changed_scores) + [False] * len(unchanged_treatment_scores),
                    changed_scores + unchanged_treatment_scores,
                ),
                4,
            ),
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in (
        ("aggregation_results.csv", results),
        ("per_fold_aggregation_results.csv", per_fold_results),
        ("aggregation_diagnostics.csv", diagnostics),
    ):
        with (args.output_dir / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    report = {
        "analysis": "OOF pair aggregation diagnostic",
        "aggregation_methods_fixed_before_analysis": list(methods),
        "selection_warning": "Do not select an aggregation on these test results and report it as confirmatory.",
        "results": results,
        "per_fold_results": per_fold_results,
        "diagnostics": diagnostics,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
