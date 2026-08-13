#!/usr/bin/env python3
"""OOF threshold diagnostics for PIBR: distinguish conservatism from collapse.

The Web control labels used to construct the FA-constrained frontier are diagnostic
only.  They are never used to train an encoder, fit the kNN memory, or select the
reported deployment threshold.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, pstdev
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.cross_domain_monitor_transfer import auroc, load, percentile
from experiments.paradigm_invariant_delegation_representation import (
    decorate,
    intervention_pairs,
    ordered,
    progress_pairs,
)
from experiments.pidr_downstream_monitor import TransitionKNN, changed
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantile_value(values: list[float], q: float) -> float:
    values = sorted(values)
    index = (len(values) - 1) * q
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - index) + values[upper] * (index - lower)


def reconstruct_oof(rollouts: Path) -> tuple[dict[str, list[dict]], dict[str, list[float]]]:
    cohorts = load(rollouts)
    decorate(cohorts)
    coding = cohorts["gpt5_minimal_coding_agent"]
    web = cohorts["gpt5_minimal_web_agent"]
    records = {"raw_transition_kNN": [], "PIBR_transition_kNN": []}
    calibrations = {"raw_transition_kNN": [], "PIBR_transition_kNN": []}

    for heldout_seed in (0, 1, 2):
        train_seeds = {0, 1, 2} - {heldout_seed}
        positives = []
        for seed in sorted(train_seeds):
            positives += progress_pairs(ordered(coding, seed), ordered(web, seed))
        negatives = intervention_pairs(coding, train_seeds) + intervention_pairs(web, train_seeds)
        encoder = ParadigmInvariantDelegationRepresentation().fit(positives, negatives)
        train = [trajectory for seed in sorted(train_seeds) for trajectory in ordered(coding, seed)]
        evaluation = {
            pair: roles
            for pair, roles in web.items()
            if roles["control"]["seed"] == heldout_seed
        }

        for name, representation in (
            ("raw_transition_kNN", None),
            ("PIBR_transition_kNN", encoder),
        ):
            model = TransitionKNN(representation, 5).fit(train)
            calibration = [max(model.score(x, exclude=i)) for i, x in enumerate(train)]
            calibrations[name].extend(calibration)
            deployment_threshold = percentile(calibration, .95)
            for pair, roles in sorted(evaluation.items()):
                diff = changed(roles["control"], roles["treatment"])
                control_scores = model.score(roles["control"])
                treatment_scores = model.score(roles["treatment"])
                changed_scores = [
                    score for step, score in enumerate(treatment_scores, 1) if step in diff
                ]
                records[name].append({
                    "fold": heldout_seed,
                    "pair_id": pair,
                    "control_max": max(control_scores),
                    "changed_max": max(changed_scores) if changed_scores else float("-inf"),
                    "control_scores": control_scores,
                    "treatment_scores": treatment_scores,
                    "changed_steps": sorted(diff),
                    "deployment_threshold": deployment_threshold,
                })
    return records, calibrations


def rates(rows: list[dict], threshold: float) -> tuple[float, float]:
    false_alarm = mean(row["control_max"] > threshold for row in rows)
    detection = mean(row["changed_max"] > threshold for row in rows)
    return false_alarm, detection


def full_curve(name: str, rows: list[dict]) -> list[dict]:
    candidates = sorted(
        {row["control_max"] for row in rows} | {row["changed_max"] for row in rows},
        reverse=True,
    )
    candidates = [float("inf")] + candidates + [float("-inf")]
    output = []
    for threshold in candidates:
        false_alarm, detection = rates(rows, threshold)
        output.append({
            "representation": name,
            "threshold": threshold,
            "web_false_alarm": round(false_alarm, 6),
            "pair_detection": round(detection, 6),
        })
    return output


def constrained_points(name: str, curve: list[dict]) -> list[dict]:
    output = []
    for target in (0, .05, .10, .15, .20, .25, .50):
        feasible = [row for row in curve if row["web_false_alarm"] <= target]
        best = max(feasible, key=lambda row: (row["pair_detection"], row["web_false_alarm"]))
        output.append({
            "representation": name,
            "target_fa_ceiling": target,
            "achieved_web_fa": best["web_false_alarm"],
            "best_pair_detection": best["pair_detection"],
            "diagnostic_threshold": best["threshold"],
            "uses_web_labels_for_diagnosis": True,
        })
    return output


def distribution_summary(name: str, rows: list[dict]) -> dict:
    controls = [row["control_max"] for row in rows]
    changed = [row["changed_max"] for row in rows]
    all_step_scores = [score for row in rows for score in row["control_scores"] + row["treatment_scores"]]
    pooled_sd = math.sqrt((pstdev(controls) ** 2 + pstdev(changed) ** 2) / 2)
    return {
        "representation": name,
        "pairs": len(rows),
        "mean_control_max": round(mean(controls), 6),
        "sd_control_max": round(pstdev(controls), 6),
        "mean_changed_max": round(mean(changed), 6),
        "sd_changed_max": round(pstdev(changed), 6),
        "mean_max_gap": round(mean(changed) - mean(controls), 6),
        "standardized_max_gap": round((mean(changed) - mean(controls)) / pooled_sd, 4),
        "all_step_score_mean": round(mean(all_step_scores), 6),
        "all_step_score_sd": round(pstdev(all_step_scores), 6),
        "pair_level_auroc_changed_max_vs_control_max": round(
            auroc([False] * len(controls) + [True] * len(changed), controls + changed), 4
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    base = ROOT / "results/multi_agent_delegation"
    parser.add_argument("--rollouts", type=Path, default=base / "normalized_rollouts.jsonl")
    parser.add_argument("--output-dir", type=Path, default=base / "pibr_oof_threshold_diagnostics")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    records, calibrations = reconstruct_oof(args.rollouts)
    curve_rows, constrained_rows, distributions, deployment = [], [], [], []
    for name, rows in records.items():
        curve = full_curve(name, rows)
        curve_rows.extend(curve)
        constrained_rows.extend(constrained_points(name, curve))
        distributions.append(distribution_summary(name, rows))
        false_alarm = mean(row["control_max"] > row["deployment_threshold"] for row in rows)
        detection = mean(row["changed_max"] > row["deployment_threshold"] for row in rows)
        deployment.append({
            "representation": name,
            "calibration": "per-fold coding-control 95th percentile",
            "web_false_alarm": round(false_alarm, 6),
            "pair_detection": round(detection, 6),
        })

    write_csv(args.output_dir / "full_oof_threshold_curve.csv", curve_rows)
    write_csv(args.output_dir / "fa_constrained_detection.csv", constrained_rows)
    write_csv(args.output_dir / "score_distribution_summary.csv", distributions)
    with (args.output_dir / "oof_trajectory_scores.jsonl").open("w") as handle:
        for name, rows in records.items():
            for row in rows:
                handle.write(json.dumps({"representation": name, **row}) + "\n")
    report = {
        "analysis": "three-fold OOF threshold and representation-collapse diagnostic",
        "pairs_per_representation": 48,
        "diagnostic_curve_uses_web_control_and_divergence_labels": True,
        "diagnostic_thresholds_are_deployable": False,
        "training_or_model_selection_changed": False,
        "deployment_operating_point": deployment,
        "score_distributions": distributions,
        "fa_constrained_frontier": constrained_rows,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
