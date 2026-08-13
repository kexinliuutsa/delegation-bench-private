#!/usr/bin/env python3
"""Experiment 5: security-state compression on real SWE-Agent traces.

The evaluated target is *context support*, not authorization or safety: does a
high-impact action have an offline-audited preceding relation from Experiment 4?
Real traces contain no independent allow/block labels, so this script does not
invent them.

M3 state is constructed incrementally from the initial task event and normalized
events strictly preceding each action. It never reads the target label,
generated patch, future events, or Experiment 4 match fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from context_distance_real import (
    initial_task,
    load_trace,
    normalize_resource,
    package_tokens,
    parse_capability,
    token_present,
    url_keys,
)


AUTHORITY_SENTENCE = re.compile(
    r"[^.!?\n]*(?:do not|don't|must not|may not|allowed|allow|permission|approve|authorized|prohibit)[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)
IDENTIFIER = re.compile(r"[A-Za-z0-9_.@/-]{3,}")
TASK_RELATION_CUE = re.compile(r"\b(?:dependency|dependencies|package|install|import|module|requirements?|environment)\b", re.IGNORECASE)
MANIFEST_NAMES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "package.json", "package-lock.json"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def json_bytes(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def task_summary(task: str) -> dict[str, Any]:
    relation_segments = [
        segment
        for segment in re.split(r"(?<=[.!?\n])\s+", task)
        if TASK_RELATION_CUE.search(segment)
    ]
    return {
        "terms": sorted({token.lower() for segment in relation_segments for token in IDENTIFIER.findall(segment)}),
        "urls": sorted(url_keys(task)),
        "authority_events": [match.group(0).strip() for match in AUTHORITY_SENTENCE.finditer(task) if match.group(0).strip()],
    }


def empty_state(task: str) -> dict[str, Any]:
    summary = task_summary(task)
    return {
        "task_relation": summary,
        "resources": {},
        "external_endpoints": [],
        "package_events": [],
        "previous_authority_events": summary["authority_events"],
    }


def update_state(state: dict[str, Any], row: dict[str, str]) -> None:
    """Mutate state using one observable preceding event."""
    step = int(row["step_id"])
    parsed = parse_capability(row["capability"])
    if parsed:
        operation, raw_resource = parsed
        resource = normalize_resource(raw_resource)
        if resource and not resource.startswith("@"):
            current = state["resources"].setdefault(
                resource,
                {
                    "first_seen_step": step,
                    "last_seen_step": step,
                    "object_provenance": "agent_created" if operation == "write" and row["tool"] == "create_file" else "observed",
                    "lifecycle_state": "present",
                    "operations": [],
                },
            )
            current["last_seen_step"] = step
            if operation == "write" and row["tool"] == "create_file":
                current["object_provenance"] = "agent_created"
            elif operation == "write" and current["object_provenance"] != "agent_created":
                current["object_provenance"] = "agent_modified"
            if operation == "delete":
                current["lifecycle_state"] = "deleted"
            if operation not in current["operations"]:
                current["operations"].append(operation)

    endpoints = set(state["external_endpoints"])
    endpoints.update(url_keys(row["args_first_line"]))
    state["external_endpoints"] = sorted(endpoints)

    packages = package_tokens(row["args_first_line"])
    if packages:
        state["package_events"].append({"step": step, "packages": packages})


def action_descriptor(row: dict[str, str], family: str) -> dict[str, Any]:
    parsed = parse_capability(row["capability"])
    return {
        "family": family,
        "step": int(row["step_id"]),
        "tool": row["tool"],
        "arguments": row["args_first_line"],
        "capability": row["capability"],
        "resource": normalize_resource(parsed[1]) if parsed else "",
    }


def event_view(row: dict[str, str]) -> dict[str, Any]:
    return {
        "step": int(row["step_id"]),
        "tool": row["tool"],
        "arguments": row["args_first_line"],
        "capability": row["capability"],
    }


def history_decision(action: dict[str, Any], task: str, events: list[dict[str, Any]]) -> bool:
    """Detect a preceding relation using only the supplied history view."""
    family = action["family"]
    target = action["resource"]
    if family == "delete":
        for event in events:
            parsed = parse_capability(event["capability"])
            if parsed and normalize_resource(parsed[1]) == target:
                return True
        return False
    if family == "submit":
        return any((parsed := parse_capability(event["capability"])) and parsed[0] == "write" for event in events)
    if family == "external":
        keys = url_keys(action["arguments"])
        if keys & url_keys(task):
            return True
        return any(keys & url_keys(event["arguments"]) for event in events)
    if family == "package_change":
        packages = package_tokens(action["arguments"])
        if any(token_present(task, package) for package in packages):
            return True
        for event in events:
            if any(token_present(event["arguments"], package) for package in packages):
                return True
            parsed = parse_capability(event["capability"])
            if parsed and Path(normalize_resource(parsed[1])).name.lower() in MANIFEST_NAMES:
                return True
        return False
    return False


def state_decision(action: dict[str, Any], state: dict[str, Any]) -> bool:
    """Make the same relation decision from compressed preceding state."""
    family = action["family"]
    target = action["resource"]
    if family == "delete":
        return target in state["resources"]
    if family == "submit":
        return any("write" in resource["operations"] for resource in state["resources"].values())
    if family == "external":
        keys = url_keys(action["arguments"])
        return bool(keys & (set(state["task_relation"]["urls"]) | set(state["external_endpoints"])))
    if family == "package_change":
        packages = package_tokens(action["arguments"])
        terms = state["task_relation"]["terms"]
        if any(any(token_present(term, package) for term in terms) for package in packages):
            return True
        if any(set(packages) & set(event["packages"]) for event in state["package_events"]):
            return True
        return any(Path(resource).name.lower() in MANIFEST_NAMES for resource in state["resources"])
    return False


def monitor_inputs(
    monitor: str,
    action: dict[str, Any],
    task: str,
    preceding: list[dict[str, str]],
    state: dict[str, Any],
) -> tuple[dict[str, Any], bool, int]:
    action_only = {"action": action}
    if monitor == "M0_action_only":
        return action_only, False, 0
    if monitor == "M1_last_10":
        events = [event_view(row) for row in preceding[-10:]]
        view = {"action": action, "task": task if action["step"] <= 10 else "", "events": events}
        return view, history_decision(action, view["task"], events), len(events) + bool(view["task"])
    if monitor == "M2_full_history":
        events = [event_view(row) for row in preceding]
        view = {"action": action, "task": task, "events": events}
        return view, history_decision(action, task, events), len(events) + 1
    if monitor == "M3_compressed_state":
        view = {"action": action, "security_state": state}
        return view, state_decision(action, state), len(state["resources"]) + len(state["package_events"]) + len(state["external_endpoints"]) + len(state["previous_authority_events"])
    raise ValueError(monitor)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 900, 430
    left, top, bottom = 75, 45, 80
    plot_h = height - top - bottom
    panel_w = 330
    panels = ((left, "decision_accuracy", "Context-support accuracy"), (500, "mean_input_bytes", "Mean serialized input bytes"))
    colors = ["#6C757D", "#E76F51", "#2A9D8F", "#276FBF"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="450" y="23" text-anchor="middle" font-family="sans-serif" font-size="17">Security state compression on real SWE-Agent traces</text>']
    for panel_left, metric, title in panels:
        maximum = 1.0 if metric == "decision_accuracy" else max(float(row[metric]) for row in rows) * 1.1
        parts.append(f'<text x="{panel_left+panel_w/2}" y="{top-8}" text-anchor="middle" font-family="sans-serif" font-size="13">{title}</text>')
        for tick in range(5):
            value = maximum * tick / 4
            y = top + plot_h * (1 - tick / 4)
            parts.append(f'<line x1="{panel_left}" y1="{y:.1f}" x2="{panel_left+panel_w}" y2="{y:.1f}" stroke="#ddd"/>')
            label = f'{value:.2f}' if metric == "decision_accuracy" else f'{value:.0f}'
            parts.append(f'<text x="{panel_left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{label}</text>')
        group = panel_w / len(rows)
        for index, row in enumerate(rows):
            value = float(row[metric])
            bar_h = plot_h * value / maximum
            x = panel_left + group * index + group * 0.2
            y = top + plot_h - bar_h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{group*0.6:.1f}" height="{bar_h:.1f}" fill="{colors[index]}"/>')
            short = row["monitor"].split("_")[0]
            parts.append(f'<text x="{x+group*0.3:.1f}" y="{top+plot_h+18}" text-anchor="middle" font-family="sans-serif" font-size="11">{short}</text>')
    parts.append('<text x="450" y="410" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#555">Accuracy target: offline context relation, not authorization or safety</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--traces", type=Path, default=root.parent / "traces/public_swe_100")
    parser.add_argument("--targets", type=Path, default=root / "results/context_distance_real.csv")
    parser.add_argument("--output", type=Path, default=root / "results/security_state_compression.csv")
    parser.add_argument("--details", type=Path, default=root / "results/security_state_compression_details.csv")
    parser.add_argument("--plot", type=Path, default=root / "results/security_state_compression.svg")
    args = parser.parse_args()

    targets = {(row["trace"], int(row["action_step"]), row["action_family"]): row["context_found"] == "True" for row in read_csv(args.targets)}
    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.steps):
        by_trace[row["trace"]].append(row)

    monitors = ("M0_action_only", "M1_last_10", "M2_full_history", "M3_compressed_state")
    details = []
    for trace_name, trace_rows in sorted(by_trace.items()):
        trace_rows.sort(key=lambda row: int(row["step_id"]))
        task = initial_task(load_trace(args.traces / trace_name))
        state = empty_state(task)
        preceding: list[dict[str, str]] = []
        for row in trace_rows:
            step = int(row["step_id"])
            matching_keys = [key for key in targets if key[0] == trace_name and key[1] == step]
            for key in matching_keys:
                family = key[2]
                action = action_descriptor(row, family)
                truth = targets[key]
                for monitor in monitors:
                    view, prediction, units = monitor_inputs(monitor, action, task, preceding, state)
                    details.append({
                        "trace": trace_name,
                        "action_step": step,
                        "action_family": family,
                        "monitor": monitor,
                        "context_target": truth,
                        "prediction": prediction,
                        "correct": truth == prediction,
                        "input_bytes": json_bytes(view),
                        "memory_units": units,
                    })
            update_state(state, row)
            preceding.append(row)

    aggregate = []
    full_predictions = {
        (row["trace"], row["action_step"], row["action_family"]): row["prediction"]
        for row in details
        if row["monitor"] == "M2_full_history"
    }
    for monitor in monitors:
        subset = [row for row in details if row["monitor"] == monitor]
        sizes = [int(row["input_bytes"]) for row in subset]
        units = [int(row["memory_units"]) for row in subset]
        full_mean = sum(int(row["input_bytes"]) for row in details if row["monitor"] == "M2_full_history") / len(subset)
        mean_size = sum(sizes) / len(sizes)
        aggregate.append({
            "monitor": monitor,
            "n_actions": len(subset),
            "correct": sum(bool(row["correct"]) for row in subset),
            "decision_accuracy": round(sum(bool(row["correct"]) for row in subset) / len(subset), 4),
            "agreement_with_full_history": round(
                sum(
                    row["prediction"]
                    == full_predictions[(row["trace"], row["action_step"], row["action_family"])]
                    for row in subset
                )
                / len(subset),
                4,
            ),
            "mean_input_bytes": round(mean_size, 2),
            "median_input_bytes": median(sizes),
            "total_input_bytes": sum(sizes),
            "peak_memory_bytes": max(sizes),
            "mean_memory_units": round(sum(units) / len(units), 2),
            "compression_ratio_vs_full": round(mean_size / full_mean, 4),
        })

    write_csv(args.output, aggregate)
    write_csv(args.details, details)
    write_svg(args.plot, aggregate)
    for row in aggregate:
        print(json.dumps(row, sort_keys=True))
    print(f"saved: {args.output}")
    print(f"saved: {args.details}")
    print(f"saved: {args.plot}")


if __name__ == "__main__":
    main()
