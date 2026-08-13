#!/usr/bin/env python3
"""Audit exposure-timing and trajectory-length confounds in PIBR mean scores."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.cross_domain_monitor_transfer import auroc


def summarize(rows: list[dict], score_key: str, subset: str) -> dict:
    controls = [row[f"control_{score_key}"] for row in rows]
    treatments = [row[f"treatment_{score_key}"] for row in rows]
    deltas = [treatment - control for control, treatment in zip(controls, treatments)]
    return {
        "subset": subset,
        "score": score_key,
        "pairs": len(rows),
        "control_mean": round(mean(controls), 6),
        "treatment_mean": round(mean(treatments), 6),
        "mean_paired_delta": round(mean(deltas), 6),
        "pairs_treatment_above_control": sum(delta > 0 for delta in deltas),
        "trajectory_auroc": round(
            auroc([False] * len(rows) + [True] * len(rows), controls + treatments), 4
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    base = ROOT / "results/multi_agent_delegation"
    parser.add_argument(
        "--scores",
        type=Path,
        default=base / "pibr_oof_threshold_diagnostics/oof_trajectory_scores.jsonl",
    )
    parser.add_argument("--rollouts", type=Path, default=base / "normalized_rollouts.jsonl")
    parser.add_argument("--output-dir", type=Path, default=base / "pibr_mean_confound_audit")
    args = parser.parse_args()

    raw_pairs: dict[str, dict] = {}
    for line in args.rollouts.read_text().splitlines():
        trajectory = json.loads(line)
        if trajectory["agent_id"] != "gpt5_minimal_web_agent":
            continue
        raw_pairs.setdefault(trajectory["pair_id"], {})[trajectory["condition"]] = trajectory

    score_rows = []
    for line in args.scores.read_text().splitlines():
        row = json.loads(line)
        if row["representation"] != "PIBR_transition_kNN":
            continue
        roles = raw_pairs[row["pair_id"]]
        exposure_step = roles["treatment"]["behavior_metrics"].get("exposure_step")
        control_scores = row["control_scores"]
        treatment_scores = row["treatment_scores"]
        common_length = min(len(control_scores), len(treatment_scores))
        pre_count = max(0, int(exposure_step) - 1) if exposure_step is not None else 0
        score_rows.append({
            "pair_id": row["pair_id"],
            "fold": row["fold"],
            "exposure_step": exposure_step,
            "pre_exposure_steps": pre_count,
            "control_length": len(control_scores),
            "treatment_length": len(treatment_scores),
            "length_delta": len(treatment_scores) - len(control_scores),
            "control_full_mean": mean(control_scores),
            "treatment_full_mean": mean(treatment_scores),
            "control_common_prefix_mean": mean(control_scores[:common_length]),
            "treatment_common_prefix_mean": mean(treatment_scores[:common_length]),
        })

    equal_length = [row for row in score_rows if row["control_length"] == row["treatment_length"]]
    summaries = [
        summarize(score_rows, "full_mean", "all_pairs"),
        summarize(score_rows, "common_prefix_mean", "all_pairs_length_truncated"),
        summarize(equal_length, "full_mean", "equal_length_pairs_only"),
    ]
    control_lengths = [row["control_length"] for row in score_rows]
    treatment_lengths = [row["treatment_length"] for row in score_rows]
    length_deltas = [row["length_delta"] for row in score_rows]
    length_summary = {
        "pairs": len(score_rows),
        "control_length_mean": round(mean(control_lengths), 4),
        "control_length_median": median(control_lengths),
        "control_length_min": min(control_lengths),
        "control_length_max": max(control_lengths),
        "treatment_length_mean": round(mean(treatment_lengths), 4),
        "treatment_length_median": median(treatment_lengths),
        "treatment_length_min": min(treatment_lengths),
        "treatment_length_max": max(treatment_lengths),
        "mean_paired_length_delta": round(mean(length_deltas), 4),
        "pairs_treatment_longer": sum(delta > 0 for delta in length_deltas),
        "pairs_equal_length": sum(delta == 0 for delta in length_deltas),
        "pairs_treatment_shorter": sum(delta < 0 for delta in length_deltas),
        "length_only_auroc": round(
            auroc(
                [False] * len(score_rows) + [True] * len(score_rows),
                control_lengths + treatment_lengths,
            ),
            4,
        ),
    }
    exposure_summary = {
        "treatment_pairs": len(score_rows),
        "exposure_step_distribution": {
            str(step): sum(row["exposure_step"] == step for row in score_rows)
            for step in sorted({row["exposure_step"] for row in score_rows})
        },
        "pairs_with_nonempty_pre_exposure_prefix": sum(row["pre_exposure_steps"] > 0 for row in score_rows),
        "pre_exposure_mean_identifiable": any(row["pre_exposure_steps"] > 0 for row in score_rows),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "pair_level_audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(score_rows[0]))
        writer.writeheader()
        writer.writerows(score_rows)
    with (args.output_dir / "length_controlled_mean_results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    report = {
        "analysis": "PIBR mean-score exposure timing and trajectory length confound audit",
        "exposure_timing": exposure_summary,
        "trajectory_length": length_summary,
        "mean_score_results": summaries,
        "interpretation_constraint": (
            "All Web treatments are exposed at step 1, so a treatment pre-exposure score "
            "comparison is not identifiable in this protocol."
        ),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
