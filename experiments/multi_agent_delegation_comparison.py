#!/usr/bin/env python3
"""Experiment 57: compare observable delegation behavior across agent cohorts."""
from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open()))


def heatmap(path: Path, values: list[dict]) -> None:
    metrics = [
        ("Exposure", "exposure_rate"),
        ("Adoption", "adoption_rate"),
        ("Capability drift", "capability_expansion_rate"),
    ]
    width, row_h, label_w, cell_w = 760, 62, 300, 140
    height = 95 + row_h * len(values)
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="380" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">Agent delegation behavior</text>']
    for index, (label, _) in enumerate(metrics):
        items.append(f'<text x="{label_w + cell_w*(index+.5)}" y="68" text-anchor="middle" font-family="sans-serif" font-size="13">{html.escape(label)}</text>')
    for row_index, row in enumerate(values):
        y = 80 + row_index * row_h
        label = f'{row["agent_id"]} ({row["agent_type"]})'
        items.append(f'<text x="{label_w-12}" y="{y+35}" text-anchor="end" font-family="sans-serif" font-size="13">{html.escape(label)}</text>')
        for column, (_, key) in enumerate(metrics):
            value = float(row[key]); intensity = int(245 - 170 * min(1, max(0, value)))
            color = f'rgb({intensity},{intensity+5},245)'
            x = label_w + column * cell_w
            items.extend((f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{row_h-4}" fill="{color}" stroke="#ddd"/>', f'<text x="{x+(cell_w-4)/2}" y="{y+35}" text-anchor="middle" font-family="sans-serif" font-size="15">{value:.1%}</text>'))
    items.append('</svg>')
    path.write_text("\n".join(items) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    base = ROOT / "results/multi_agent_delegation"
    parser.add_argument("--input-dir", type=Path, default=base)
    parser.add_argument("--output-dir", type=Path, default=base / "agent_comparison")
    args = parser.parse_args()
    exposure = {row["agent_id"]: row for row in rows(args.input_dir / "environment_exposure_rate.csv")}
    adoption = {row["agent_id"]: row for row in rows(args.input_dir / "agent_adoption_profile.csv")}
    divergence = {row["agent_id"]: row for row in rows(args.input_dir / "agent_divergence_comparison.csv")}
    agent_ids = sorted(set(exposure) & set(adoption) & set(divergence))
    comparison = []
    for agent_id in agent_ids:
        comparison.append({
            "agent_id": agent_id,
            "agent_type": exposure[agent_id]["agent_type"],
            "agent_model": exposure[agent_id]["agent_model"],
            "pairs": int(divergence[agent_id]["pairs"]),
            "exposure_rate": float(exposure[agent_id]["environment_exposure_rate"]),
            "adoption_rate": float(adoption[agent_id]["adoption_rate_given_exposure"]),
            "capability_expansion_rate": float(adoption[agent_id]["capability_expansion_rate"]),
            "action_divergence": float(divergence[agent_id]["mean_action_divergence"]),
            "capability_divergence": float(divergence[agent_id]["mean_capability_divergence"]),
        })
    if not comparison:
        raise SystemExit("no complete agent cohorts")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "agent_comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0])); writer.writeheader(); writer.writerows(comparison)
    heatmap(args.output_dir / "agent_behavior_heatmap.svg", comparison)
    summary = {
        "experiment": 57, "agent_cohorts": len(comparison),
        "cross_agent_comparison_supported": len(comparison) >= 2,
        "status": "complete" if len(comparison) >= 2 else "framework_complete_awaiting_second_agent",
        "results": comparison,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
