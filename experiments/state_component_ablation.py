#!/usr/bin/env python3
"""Experiment 6: component ablation of compressed execution security state.

Each ablation is a literal removal from the state built by Experiment 5. The
state decision rule is fixed across conditions. Context-relation targets are
used only for evaluation and never enter state construction or ablation.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Callable

from context_distance_real import initial_task, load_trace
from security_state_compression import (
    action_descriptor,
    empty_state,
    json_bytes,
    read_csv,
    state_decision,
    update_state,
)


def full_state(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


def remove_resource_identity(state: dict[str, Any]) -> dict[str, Any]:
    """Remove resource names while preserving all per-resource attributes."""
    value = copy.deepcopy(state)
    value["resources"] = {
        str(index): resource
        for index, resource in enumerate(value["resources"].values())
    }
    return value


def remove_provenance(state: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(state)
    for resource in value["resources"].values():
        resource.pop("object_provenance", None)
    return value


def remove_lifecycle(state: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(state)
    for resource in value["resources"].values():
        resource.pop("lifecycle_state", None)
    return value


def remove_authority_history(state: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(state)
    value["previous_authority_events"] = []
    # The same clauses are not retained through the task summary back door.
    value["task_relation"]["authority_events"] = []
    return value


def remove_task_relation(state: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(state)
    value["task_relation"] = {"terms": [], "urls": [], "authority_events": []}
    return value


ABLATIONS: tuple[tuple[str, str, Callable[[dict[str, Any]], dict[str, Any]]], ...] = (
    ("M0_full_state", "none", full_state),
    ("M1_no_resource_identity", "resource_identity", remove_resource_identity),
    ("M2_no_provenance", "provenance", remove_provenance),
    ("M3_no_lifecycle", "lifecycle", remove_lifecycle),
    ("M4_no_authority_history", "authority_history", remove_authority_history),
    ("M5_no_task_relation", "task_relation", remove_task_relation),
)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 1060, 470
    top, bottom = 55, 100
    plot_h = height - top - bottom
    panels = (
        (70, 390, "context_recovery_accuracy", "Context-recovery accuracy", 1.0),
        (600, 390, "mean_state_bytes", "Mean state bytes", max(float(row["mean_state_bytes"]) for row in rows) * 1.1),
    )
    colors = ["#276FBF", "#E76F51", "#2A9D8F", "#E9C46A", "#8E5EA2", "#6C757D"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="530" y="24" text-anchor="middle" font-family="sans-serif" font-size="17">Security state component ablation</text>',
        '<text x="530" y="42" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#555">Target is preceding context relation, not authorization or safety</text>',
    ]
    for left, panel_w, metric, title, maximum in panels:
        parts.append(f'<text x="{left+panel_w/2}" y="{top-10}" text-anchor="middle" font-family="sans-serif" font-size="13">{title}</text>')
        for tick in range(5):
            value = maximum * tick / 4
            y = top + plot_h * (1 - tick / 4)
            parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+panel_w}" y2="{y:.1f}" stroke="#ddd"/>')
            label = f'{value:.2f}' if maximum == 1.0 else f'{value:.0f}'
            parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{label}</text>')
        group = panel_w / len(rows)
        for index, row in enumerate(rows):
            value = float(row[metric])
            bar_h = plot_h * value / maximum
            x = left + group * index + group * 0.18
            y = top + plot_h - bar_h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{group*0.64:.1f}" height="{bar_h:.1f}" fill="{colors[index]}"/>')
            label = row["monitor"].replace("_", " ")
            tx = x + group * 0.32
            ty = top + plot_h + 16
            parts.append(f'<text x="{tx:.1f}" y="{ty}" transform="rotate(35 {tx:.1f} {ty})" text-anchor="start" font-family="sans-serif" font-size="9">{label}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--traces", type=Path, default=root.parent / "traces/public_swe_100")
    parser.add_argument("--targets", type=Path, default=root / "results/context_distance_real.csv")
    parser.add_argument("--output", type=Path, default=root / "results/state_component_ablation.csv")
    parser.add_argument("--plot", type=Path, default=root / "results/state_component_ablation.svg")
    args = parser.parse_args()

    # Evaluation targets remain in a separate lookup and never enter state.
    targets = {
        (row["trace"], int(row["action_step"]), row["action_family"]): row["context_found"] == "True"
        for row in read_csv(args.targets)
    }
    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.steps):
        by_trace[row["trace"]].append(row)

    details = []
    for trace_name, trace_rows in sorted(by_trace.items()):
        trace_rows.sort(key=lambda row: int(row["step_id"]))
        state = empty_state(initial_task(load_trace(args.traces / trace_name)))
        for row in trace_rows:
            step = int(row["step_id"])
            matching = [key for key in targets if key[0] == trace_name and key[1] == step]
            for key in matching:
                action = action_descriptor(row, key[2])
                for monitor, removed, transform in ABLATIONS:
                    ablated = transform(state)
                    details.append(
                        {
                            "trace": trace_name,
                            "action_step": step,
                            "action_family": key[2],
                            "monitor": monitor,
                            "component_removed": removed,
                            "target": targets[key],
                            "prediction": state_decision(action, ablated),
                            "state_bytes": json_bytes(ablated),
                        }
                    )
            # Strict temporal order: current event enters state only afterward.
            update_state(state, row)

    full_predictions = {
        (row["trace"], row["action_step"], row["action_family"]): row["prediction"]
        for row in details
        if row["monitor"] == "M0_full_state"
    }
    result = []
    for monitor, removed, _ in ABLATIONS:
        subset = [row for row in details if row["monitor"] == monitor]
        sizes = [int(row["state_bytes"]) for row in subset]
        full_mean = sum(int(row["state_bytes"]) for row in details if row["monitor"] == "M0_full_state") / len(subset)
        correct = sum(row["target"] == row["prediction"] for row in subset)
        agreement = sum(
            row["prediction"] == full_predictions[(row["trace"], row["action_step"], row["action_family"])]
            for row in subset
        )
        result.append(
            {
                "monitor": monitor,
                "component_removed": removed,
                "n_actions": len(subset),
                "correct": correct,
                "context_recovery_accuracy": round(correct / len(subset), 4),
                "agreement_with_full_state": round(agreement / len(subset), 4),
                "mean_state_bytes": round(sum(sizes) / len(sizes), 2),
                "median_state_bytes": median(sizes),
                "peak_state_bytes": max(sizes),
                "memory_ratio_vs_full": round((sum(sizes) / len(sizes)) / full_mean, 4),
            }
        )

    write_csv(args.output, result)
    write_svg(args.plot, result)
    for row in result:
        print(json.dumps(row, sort_keys=True))
    print(f"saved: {args.output}")
    print(f"saved: {args.plot}")


if __name__ == "__main__":
    main()
