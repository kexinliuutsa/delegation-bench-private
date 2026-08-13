#!/usr/bin/env python3
"""Evaluate DelegationBench hard-split baselines under trajectory noise.

Noise changes the observable trajectory, not the delegation semantics. A failed
operation attempt retains the state required to attempt it; success/failure is
not itself an authority label.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from delegationbench_compositional_split import PUBLIC, build_predictors, evaluate, generate_split, validate
from models.delegation_state import DEFAULT_STATE, DelegationState


IRRELEVANT_OBSERVATIONS = (
    "An unrelated promotional banner was also visible.",
    "The page footer displayed a generic copyright notice.",
    "A non-task notification badge appeared in the navigation bar.",
)


def rebuild_sample(sample: dict[str, Any], planned: list[dict[str, Any]]) -> dict[str, Any]:
    current = DEFAULT_STATE
    trajectory = []
    oracle_states = [current.to_dict()]
    for step, event in enumerate(planned, start=1):
        required = DelegationState.from_dict(event["required_state"])
        current = current.join(required)
        trajectory.append({**event, "step": step})
        oracle_states.append(current.to_dict())
    return {
        **{key: sample[key] for key in ("id", "category", "task", "initial_state")},
        "id": sample["id"] + "__noisy",
        "trajectory": trajectory,
        "oracle_states": oracle_states,
    }


def add_noise(sample: dict[str, Any], sample_index: int) -> tuple[dict[str, Any], Counter[str]]:
    original = sample["trajectory"]
    planned: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    final_required = original[-1]["required_state"]

    for index, event in enumerate(original):
        copied = {key: event[key] for key in ("action", "observation", "required_state")}
        if index % 2 == 1:
            copied["observation"] += " " + IRRELEVANT_OBSERVATIONS[(sample_index + index) % len(IRRELEVANT_OBSERVATIONS)]
            counts["irrelevant_observation"] += 1

        # A failed ambiguous submission is inserted immediately before the
        # successful terminal action. It requires the same delegation envelope
        # as the attempted terminal operation, although its effect did not occur.
        if index == len(original) - 1:
            planned.append({
                "action": "click submit",
                "observation": "The attempted action failed with a transient timeout; no effect was reported.",
                "required_state": final_required,
            })
            counts["failed_action"] += 1
            planned.append({
                "action": "return to previous page",
                "observation": "The prior task page was restored.",
                "required_state": PUBLIC.to_dict(),
            })
            counts["recovery_action"] += 1

        planned.append(copied)
        if index == 0:
            planned.append({
                "action": copied["action"],
                "observation": "The agent repeated the preceding action and observed the same content.",
                "required_state": copied["required_state"],
            })
            counts["redundant_action"] += 1
    return rebuild_sample(sample, planned), counts


def condition_rows(clean_results: list[dict[str, Any]], noisy_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = {row["method"]: row for row in clean_results}
    noisy = {row["method"]: row for row in noisy_results}
    output = []
    for method in clean:
        for condition, source in (("clean", clean[method]), ("noisy", noisy[method])):
            recovery = float(source["state_recovery_accuracy"])
            transition = float(source["transition_detection_f1"])
            clean_recovery = float(clean[method]["state_recovery_accuracy"])
            clean_transition = float(clean[method]["transition_detection_f1"])
            output.append({
                "method": method,
                "condition": condition,
                "state_recovery_accuracy": recovery,
                "transition_detection_f1": transition,
                "state_recovery_absolute_degradation": round(clean_recovery - recovery, 4),
                "transition_f1_absolute_degradation": round(clean_transition - transition, 4),
                "state_recovery_relative_degradation": round((clean_recovery - recovery) / clean_recovery, 4) if clean_recovery else "",
                "transition_f1_relative_degradation": round((clean_transition - transition) / clean_transition, 4) if clean_transition else "",
                "evaluated_states": source["test_states"],
            })
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-output", type=Path, default=ROOT / "benchmarks/delegationbench/noisy_compositional_split.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/delegationbench_noisy_trajectory.csv")
    args = parser.parse_args()

    split = generate_split()
    predictors = build_predictors(split["train"])
    validate(split, predictors)
    noisy = []
    noise_counts: Counter[str] = Counter()
    for index, sample in enumerate(split["test"]):
        transformed, counts = add_noise(sample, index)
        noisy.append(transformed)
        noise_counts.update(counts)

    clean_results, clean_transitions = evaluate(split["test"], predictors)
    noisy_results, noisy_transitions = evaluate(noisy, predictors)
    rows = condition_rows(clean_results, noisy_results)

    # Pair-level construction validation.
    for clean, perturbed in zip(split["test"], noisy):
        if clean["task"] != perturbed["task"]:
            raise AssertionError("noise changed task semantics")
        if clean["oracle_states"][-1] != perturbed["oracle_states"][-1]:
            raise AssertionError("noise changed final delegation envelope")
        if len(perturbed["trajectory"]) != len(clean["trajectory"]) + 3:
            raise AssertionError("unexpected noisy trajectory length")
        failed = [event for event in perturbed["trajectory"] if event["action"] == "click submit"]
        if len(failed) != 1 or failed[0]["required_state"] != clean["trajectory"][-1]["required_state"]:
            raise AssertionError("failed attempt has inconsistent required delegation")

    args.benchmark_output.parent.mkdir(parents=True, exist_ok=True)
    args.benchmark_output.write_text(json.dumps({"clean": split["test"], "noisy": noisy}, indent=2), encoding="utf-8")
    write_csv(args.output, rows)
    print(json.dumps({
        "paired_trajectories": len(noisy),
        "clean_states": sum(len(sample["trajectory"]) for sample in split["test"]),
        "noisy_states": sum(len(sample["trajectory"]) for sample in noisy),
        "noise_distribution": noise_counts,
        "clean_transitions": clean_transitions,
        "noisy_transitions": noisy_transitions,
        "comparison": rows,
        "interpretation": "Degradation measures robustness to controlled trajectory noise, not agent safety.",
    }, indent=2))


if __name__ == "__main__":
    main()
