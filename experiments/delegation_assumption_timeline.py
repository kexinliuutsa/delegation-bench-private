#!/usr/bin/env python3
"""Experiment 12: mine delegation-assumption timelines from SWE-Agent actions.

This is a descriptive, rule-based reconstruction. An extracted assumption means
that an action operationally relies on that kind of delegation; it does not mean
the delegation was absent, unsafe, or unauthorized.

Leakage boundary: only ``trace``, ``step_id``, ``tool``, ``args_first_line``, and
``capability`` are read from the raw action table. Risk/escalation labels,
previous classifications, generated patches, and audit decisions are never read.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shlex
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ASSUMPTIONS = (
    "A1_repository_read",
    "A2_repository_write",
    "A3_local_execution",
    "A4_environment_change",
    "A5_artifact_creation",
    "A6_artifact_deletion",
    "A7_external_interaction",
    "A8_submission_or_publishing",
)
ORDER = {name: index for index, name in enumerate(ASSUMPTIONS)}
HIGH_IMPACT = {
    "A4_environment_change", "A6_artifact_deletion",
    "A7_external_interaction", "A8_submission_or_publishing",
}
INPUT_COLUMNS_USED = {"trace", "step_id", "tool", "args_first_line", "capability"}
FORBIDDEN_INPUT_CONCEPTS = {
    "is_escalation", "is_irreversible_escalation", "risk", "task_relation",
    "audit_category", "generated_patch", "target",
}

CAPABILITY = re.compile(r"^(?P<operation>[^:]+):(?P<resource>.*)\([^()]*\)$")
INSTALL = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:(?:python\d*(?:\.\d+)?\s+-m\s+)?pip\d*|uv)\s+install\b|"
    r"(?:^|[;&|]\s*|\s)(?:npm|yarn|pnpm)\s+(?:install|add)\b|"
    r"(?:^|[;&|]\s*|\s)(?:apt|apt-get|apk|brew|conda)\s+(?:install|add|update|upgrade)\b",
    re.IGNORECASE,
)
ENVIRONMENT = re.compile(
    r"\b(?:virtualenv|python\s+-m\s+venv|conda\s+(?:create|install|update)|"
    r"export\s+[A-Za-z_][A-Za-z0-9_]*=|chmod\b|update-alternatives\b)" , re.IGNORECASE
)
NETWORK = re.compile(
    r"\b(?:curl|wget|ssh|scp|rsync|search_engine|lynx|httpie)\b|https?://", re.IGNORECASE
)
PUBLISH = re.compile(
    r"\bgit\s+push\b|\b(?:twine\s+upload|npm\s+publish|cargo\s+publish|"
    r"gh\s+(?:pr\s+create|release\s+create)|submit|publish|upload)\b", re.IGNORECASE
)
CREATE = re.compile(
    r"(?:^|[;&|]\s*)(?:mkdir|touch|mktemp)\b|(?:^|[;&|]\s*)(?:cp|install)\s+|"
    r"(?:^|[;&|]\s*)(?:echo|printf)\b[^\n]*(?:>|tee\b)", re.IGNORECASE
)
DELETE = re.compile(r"(?:^|[;&|]\s*)(?:rm|rmdir|unlink)\b", re.IGNORECASE)
WRITE = re.compile(
    r"(?:^|[;&|]\s*)(?:sed\s+-i|perl\s+-[A-Za-z]*i|mv)\b|(?:>>?|\btee\b)", re.IGNORECASE
)
READ = re.compile(
    r"(?:^|[;&|]\s*)(?:cat|head|tail|less|more|ls|find|grep|rg|pwd|file|stat|"
    r"git\s+(?:status|diff|log|show)|python\s+-m\s+pytest|pytest)\b", re.IGNORECASE
)
TEST_OR_SCRIPT = re.compile(
    r"(?:^|[;&|]\s*)(?:pytest|tox|nox|make|cmake|python\d*(?:\.\d+)?|bash|sh|"
    r"\.\/|[A-Za-z0-9_.-]+\.py\b|[A-Za-z0-9_.-]+\.sh\b)", re.IGNORECASE
)
MANIFEST = re.compile(
    r"(?:^|/)(?:requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|Pipfile(?:\.lock)?|"
    r"package(?:-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.(?:toml|lock))$",
    re.IGNORECASE,
)


def parse_capability(value: str) -> tuple[str, str]:
    match = CAPABILITY.match(value)
    return (match["operation"], match["resource"]) if match else ("", "")


def normalize_command(action: str) -> str:
    try:
        return " ".join(shlex.split(action))
    except ValueError:
        return re.sub(r"\s+", " ", action).strip()


def extract_assumptions(row: dict[str, str]) -> list[str]:
    """Map observable operation semantics to zero or more assumptions."""
    operation, resource = parse_capability(row["capability"])
    tool = row["tool"]
    action = normalize_command(row["args_first_line"])
    found: set[str] = set()

    if operation == "read":
        found.add("A1_repository_read")
    elif operation == "write":
        found.add("A5_artifact_creation" if tool == "create_file" else "A2_repository_write")
        if MANIFEST.search(resource):
            found.add("A4_environment_change")
    elif operation == "exec":
        found.add("A3_local_execution")
        if READ.search(action) or "@test-suite" in row["capability"] or re.search(r"\b(?:pytest|tox|nox)\b", action):
            found.add("A1_repository_read")
    elif operation == "delete":
        found.add("A6_artifact_deletion")
    elif operation == "network":
        found.add("A7_external_interaction")
    elif operation == "submit" or tool == "submit":
        found.add("A8_submission_or_publishing")

    # Action-level rules cover compound commands and parser omissions.
    if INSTALL.search(action) or ENVIRONMENT.search(action):
        found.update({"A3_local_execution", "A4_environment_change"})
    if PUBLISH.search(action):
        found.update({"A7_external_interaction", "A8_submission_or_publishing"})
    elif NETWORK.search(action):
        found.add("A7_external_interaction")
    if DELETE.search(action):
        found.add("A6_artifact_deletion")
    if CREATE.search(action):
        found.add("A5_artifact_creation")
    if WRITE.search(action) and "A5_artifact_creation" not in found:
        found.add("A2_repository_write")
    if READ.search(action):
        found.add("A1_repository_read")
    if not operation and TEST_OR_SCRIPT.search(action):
        found.add("A3_local_execution")
    # Parser-opaque Bash commands still require local command execution.  Do
    # not guess their read/write/environment effects from unfamiliar names.
    if not found and tool == "bash" and action:
        found.add("A3_local_execution")
    return sorted(found, key=ORDER.get)


def read_actions(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = INPUT_COLUMNS_USED - fields
        if missing:
            raise SystemExit(f"Input lacks required observable columns: {sorted(missing)}")
        # Deliberately project the input immediately, excluding all other fields.
        return [{key: row[key] for key in INPUT_COLUMNS_USED} for row in reader]


def leakage_audit() -> dict[str, Any]:
    overlap = INPUT_COLUMNS_USED & FORBIDDEN_INPUT_CONCEPTS
    if overlap:
        raise AssertionError(f"Forbidden columns selected: {sorted(overlap)}")
    return {
        "status": "pass",
        "input_columns_used": sorted(INPUT_COLUMNS_USED),
        "forbidden_columns_used": [],
        "generated_patches_read": False,
        "previous_classification_or_audit_labels_read": False,
    }


def assumption_waves(events: list[dict[str, Any]]) -> list[tuple[int, list[str]]]:
    by_step: dict[int, list[str]] = defaultdict(list)
    for event in events:
        if event["is_new_assumption"]:
            by_step[event["step"]].append(event["assumption"])
    return [(step, sorted(set(values), key=ORDER.get)) for step, values in sorted(by_step.items())]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: list[int], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def write_svg(path: Path, active_by_trace: dict[str, list[tuple[int, int]]]) -> None:
    width, height = 1000, 610
    left, right, top, bottom = 80, 30, 55, 70
    plot_w, plot_h = width - left - right, height - top - bottom
    max_step = max(step for points in active_by_trace.values() for step, _ in points)
    max_depth = max(depth for points in active_by_trace.values() for _, depth in points)
    sx = lambda value: left + plot_w * value / max(1, max_step)
    sy = lambda value: top + plot_h * (1 - value / max(1, max_depth))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="500" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation assumption scope across SWE-Agent execution</text>',
    ]
    for value in range(max_depth + 1):
        y = sy(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{value}</text>')
    for points in active_by_trace.values():
        coords = " ".join(f"{sx(step):.1f},{sy(depth):.1f}" for step, depth in points)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="#3b82f6" stroke-opacity="0.12" stroke-width="1"/>')
    # Raw-step aggregate: median and interquartile range among traces still active.
    aggregate = []
    for step in range(1, max_step + 1):
        depths = []
        for points in active_by_trace.values():
            eligible = [depth for point_step, depth in points if point_step <= step]
            if eligible and points[-1][0] >= step:
                depths.append(eligible[-1])
        if depths:
            aggregate.append((step, percentile(depths, .25), percentile(depths, .5), percentile(depths, .75)))
    upper = " ".join(f"{sx(s):.1f},{sy(q3):.1f}" for s, _, _, q3 in aggregate)
    lower = " ".join(f"{sx(s):.1f},{sy(q1):.1f}" for s, q1, _, _ in reversed(aggregate))
    parts.append(f'<polygon points="{upper} {lower}" fill="#2563eb" fill-opacity="0.16"/>')
    median = " ".join(f"{sx(s):.1f},{sy(q2):.1f}" for s, _, q2, _ in aggregate)
    parts.append(f'<polyline points="{median}" fill="none" stroke="#1d4ed8" stroke-width="3"/>')
    parts.extend([
        f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#111827"/>',
        f'<text x="{left+plot_w/2:.1f}" y="{height-22}" text-anchor="middle" font-family="sans-serif" font-size="14">Execution step</text>',
        f'<text x="19" y="{top+plot_h/2:.1f}" transform="rotate(-90 19 {top+plot_h/2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="14">Cumulative active assumptions</text>',
        f'<text x="{width-right}" y="{height-44}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#4b5563">Thin lines: traces · dark line: median · band: IQR among active traces</text>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--actions", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--timeline", type=Path, default=root / "results/delegation_assumption_timeline.csv")
    parser.add_argument("--summary", type=Path, default=root / "results/delegation_assumption_summary.csv")
    parser.add_argument("--transitions", type=Path, default=root / "results/delegation_assumption_transition.csv")
    parser.add_argument("--plot", type=Path, default=root / "results/delegation_assumption_timeline.svg")
    args = parser.parse_args()

    audit = leakage_audit()
    actions = read_actions(args.actions)
    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in actions:
        by_trace[row["trace"]].append(row)
    for rows in by_trace.values():
        rows.sort(key=lambda row: int(row["step_id"]))

    timeline: list[dict[str, Any]] = []
    trace_events: dict[str, list[dict[str, Any]]] = {}
    active_by_trace: dict[str, list[tuple[int, int]]] = {}
    mapped_actions = 0
    for trace, rows in sorted(by_trace.items()):
        first: dict[str, int] = {}
        occurrence_counts: Counter[str] = Counter()
        extracted = [(row, extract_assumptions(row)) for row in rows]
        totals = Counter(a for _, values in extracted for a in values)
        events = []
        depth_points = []
        for row, assumptions in extracted:
            step = int(row["step_id"])
            previous = sorted(first, key=ORDER.get)
            if assumptions:
                mapped_actions += 1
            new_at_step = [a for a in assumptions if a not in first]
            for assumption in assumptions:
                first.setdefault(assumption, step)
                occurrence_counts[assumption] += 1
            current = sorted(first, key=ORDER.get)
            depth_points.append((step, len(current)))
            for assumption in assumptions:
                event = {
                    "trace": trace, "step": step, "action": row["args_first_line"],
                    "capability": row["capability"], "assumption": assumption,
                    "first_introduction_step": first[assumption],
                    "is_new_assumption": assumption in new_at_step,
                    "previous_assumptions": json.dumps(previous),
                    "current_assumption_set": json.dumps(current),
                    "occurrence_number": occurrence_counts[assumption],
                    "total_occurrences": totals[assumption],
                    "assumption_persists": True,
                }
                timeline.append(event)
                events.append(event)
        trace_events[trace] = events
        active_by_trace[trace] = depth_points

    summary_rows = []
    transition_traces: dict[tuple[str, str], set[str]] = defaultdict(set)
    transition_frequency: Counter[tuple[str, str]] = Counter()
    for trace, events in sorted(trace_events.items()):
        waves = assumption_waves(events)
        introduced = [assumption for _, wave in waves for assumption in wave]
        high_steps = [step for step, wave in waves if set(wave) & HIGH_IMPACT]
        sequence = " -> ".join(" + ".join(wave) for _, wave in waves)
        for (_, prior), (_, current) in zip(waves, waves[1:]):
            for source in prior:
                for target in current:
                    transition_frequency[(source, target)] += 1
                    transition_traces[(source, target)].add(trace)
        summary_rows.append({
            "trace": trace,
            "total_unique_assumptions": len(set(introduced)),
            "assumption_expansion_count": len(set(introduced)),
            "first_high_impact_assumption_step": min(high_steps) if high_steps else "",
            "delegation_depth": max((depth for _, depth in active_by_trace[trace]), default=0),
            "assumption_transition_sequence": sequence,
            "actions_in_trace": len(by_trace[trace]),
            "actions_with_extracted_assumptions": len({event["step"] for event in events}),
        })

    transition_rows = [
        {
            "from_assumption": source, "to_assumption": target,
            "transition_frequency": count,
            "traces_containing_transition": len(transition_traces[(source, target)]),
        }
        for (source, target), count in sorted(
            transition_frequency.items(), key=lambda item: (-item[1], ORDER[item[0][0]], ORDER[item[0][1]])
        )
    ]
    write_csv(args.timeline, timeline, list(timeline[0]))
    write_csv(args.summary, summary_rows, list(summary_rows[0]))
    write_csv(args.transitions, transition_rows, [
        "from_assumption", "to_assumption", "transition_frequency", "traces_containing_transition"
    ])
    write_svg(args.plot, active_by_trace)

    distribution = Counter(row["assumption"] for row in timeline)
    common = [
        {"transition": f"{row['from_assumption']} -> {row['to_assumption']}",
         "frequency": row["transition_frequency"], "traces": row["traces_containing_transition"]}
        for row in transition_rows[:10]
    ]
    high_trace_count = sum(bool(row["first_high_impact_assumption_step"]) for row in summary_rows)
    report = {
        "trajectories_analyzed": len(by_trace),
        "actions_processed": len(actions),
        "actions_with_assumptions": mapped_actions,
        "assumption_distribution": {key: distribution[key] for key in ASSUMPTIONS},
        "most_common_assumption_transitions": common,
        "average_expansion_count": round(mean(int(row["assumption_expansion_count"]) for row in summary_rows), 3),
        "percentage_traces_introducing_high_impact_assumptions": round(100 * high_trace_count / len(summary_rows), 2),
        "leakage_audit": audit,
        "interpretation_limit": "Extracted assumptions are not claims of unsafe or unauthorized behavior.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
