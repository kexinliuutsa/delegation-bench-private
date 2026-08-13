#!/usr/bin/env python3
"""Measure how much session history is needed to recover delete provenance.

This experiment deliberately measures an observable event relation, not whether a
delete was authorized: a delete target either has or has not appeared in an
earlier create/write event in the same trace.  It uses only Python's standard
library so the experiment is isolated from the existing analysis pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import median


CAPABILITY = re.compile(r"^(?P<op>[^:]+):(?P<resource>.*)\((?P<effect>[^()]*)\)$")
WINDOWS = (0, 1, 2, 3, 5, 10, 20, 50)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty result: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_capability(text: str) -> tuple[str, str] | None:
    match = CAPABILITY.match(text)
    if not match:
        return None
    return match["op"], match["resource"]


def extract_events(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_trace[row["trace"]].append(row)

    deletes: list[dict[str, object]] = []
    for trace, trace_rows in sorted(by_trace.items()):
        first_create: dict[str, int] = {}
        last_write: dict[str, int] = {}
        for row in sorted(trace_rows, key=lambda item: int(item["step_id"])):
            parsed = parse_capability(row["capability"])
            if parsed is None:
                continue
            op, resource = parsed
            step = int(row["step_id"])
            if op == "write":
                last_write[resource] = step
                if row["tool"] == "create_file":
                    first_create.setdefault(resource, step)
            elif op == "delete":
                create_step = first_create.get(resource)
                write_step = last_write.get(resource)
                deletes.append(
                    {
                        "trace": trace,
                        "delete_step": step,
                        "resource": resource,
                        "action": row["args_first_line"],
                        "prior_explicit_create": create_step is not None,
                        "create_step": "" if create_step is None else create_step,
                        "create_distance": "" if create_step is None else step - create_step,
                        "prior_any_write": write_step is not None,
                        "last_write_step": "" if write_step is None else write_step,
                        "write_distance": "" if write_step is None else step - write_step,
                    }
                )
    return deletes


def window_table(events: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for definition, flag, distance_key in (
        ("explicit_create", "prior_explicit_create", "create_distance"),
        ("any_prior_write", "prior_any_write", "write_distance"),
    ):
        positives = [event for event in events if event[flag]]
        distances = [int(event[distance_key]) for event in positives]
        for window in WINDOWS:
            recovered = sum(distance <= window for distance in distances)
            total = len(positives)
            rows.append(
                {
                    "provenance_definition": definition,
                    "history_window_steps": window,
                    "recoverable_relations": recovered,
                    "total_full_session_relations": total,
                    "recall": round(recovered / total, 4) if total else "",
                    "missed_relations": total - recovered,
                    "miss_rate": round((total - recovered) / total, 4) if total else "",
                }
            )
    return rows


def svg_plot(path: Path, rows: list[dict[str, object]]) -> None:
    width, height = 760, 440
    left, right, top, bottom = 70, 25, 35, 65
    plot_w, plot_h = width - left - right, height - top - bottom
    colors = {"explicit_create": "#2457a7", "any_prior_write": "#d66a2c"}

    def x(window: int) -> float:
        return left + plot_w * math.log1p(window) / math.log1p(max(WINDOWS))

    def y(recall: float) -> float:
        return top + plot_h * (1 - recall)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="380" y="22" text-anchor="middle" font-family="sans-serif" font-size="16">Provenance recovery versus retained session history</text>',
    ]
    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        yy = y(tick)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" stroke="#ddd"/>')
        parts.append(f'<text x="{left-10}" y="{yy+5:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{tick:.2f}</text>')
    for window in WINDOWS:
        xx = x(window)
        parts.append(f'<text x="{xx:.1f}" y="{height-bottom+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{window}</text>')
    parts.extend([
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#333"/>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#333"/>',
        f'<text x="{left+plot_w/2:.1f}" y="{height-12}" text-anchor="middle" font-family="sans-serif" font-size="13">Retained prior steps (log scale)</text>',
        f'<text x="16" y="{top+plot_h/2:.1f}" transform="rotate(-90 16 {top+plot_h/2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="13">Relation recall</text>',
    ])
    for index, definition in enumerate(colors):
        series = [row for row in rows if row["provenance_definition"] == definition]
        points = " ".join(f'{x(int(row["history_window_steps"])):.1f},{y(float(row["recall"])):.1f}' for row in series)
        parts.append(f'<polyline points="{points}" fill="none" stroke="{colors[definition]}" stroke-width="3"/>')
        for row in series:
            parts.append(f'<circle cx="{x(int(row["history_window_steps"])):.1f}" cy="{y(float(row["recall"])):.1f}" r="4" fill="{colors[definition]}"/>')
        label = definition.replace("_", " ")
        parts.append(f'<line x1="525" y1="{42+index*24}" x2="555" y2="{42+index*24}" stroke="{colors[definition]}" stroke-width="3"/>')
        parts.append(f'<text x="563" y="{47+index*24}" font-family="sans-serif" font-size="12">{label}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("../results/public_swe_100/steps_raw.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/provenance_horizon"))
    args = parser.parse_args()

    events = extract_events(read_rows(args.input))
    if not events:
        raise SystemExit("No delete events found")
    windows = window_table(events)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "delete_events.csv", events)
    write_csv(args.output_dir / "window_recovery.csv", windows)
    svg_plot(args.output_dir / "window_recovery.svg", windows)

    create_distances = [int(row["create_distance"]) for row in events if row["prior_explicit_create"]]
    write_distances = [int(row["write_distance"]) for row in events if row["prior_any_write"]]
    summary = {
        "input": str(args.input),
        "traces": len({row["trace"] for row in events}),
        "delete_events": len(events),
        "explicit_create_relations": len(create_distances),
        "any_prior_write_relations": len(write_distances),
        "explicit_create_distance": {"min": min(create_distances), "median": median(create_distances), "max": max(create_distances)},
        "any_prior_write_distance": {"min": min(write_distances), "median": median(write_distances), "max": max(write_distances)},
        "interpretation_guardrail": "Relations are runtime provenance, not labels of authorization, benignity, or intent.",
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
