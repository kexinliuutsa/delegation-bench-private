#!/usr/bin/env python3
"""Build evidence packets for manual authority-ambiguity annotation.

The generated interpretations are alternatives, not classifications.  This
script never reads, writes, or predicts ``audit_category``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from authority_boundary_mining import objective_from_prompt
from context_distance_real import initial_task, load_trace, normalize_resource, parse_capability


HIGH_IMPACT = {"execute", "external", "irreversible"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def compact(text: str, limit: int = 360) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def task_summary(objective: str) -> str:
    """Return a conservative extractive summary, without adding intent."""
    clean = compact(objective, 900)
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    return compact(" ".join(sentences[:2]), 420)


def event_resource(row: dict[str, str]) -> str:
    parsed = parse_capability(row.get("capability", ""))
    return normalize_resource(parsed[1]) if parsed else ""


def event_record(row: dict[str, str], reason: str) -> dict[str, Any]:
    return {
        "step": int(row["step_id"]),
        "action": row["args_first_line"],
        "capability": row["capability"],
        "resource": event_resource(row),
        "relevance": reason,
    }


def prior_context(
    rows: list[dict[str, str]], step: int, resource: str, capability: str, limit: int = 8
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prior = [row for row in rows if int(row["step_id"]) < step]
    object_rows = [row for row in prior if resource and event_resource(row) == resource]
    object_history = [event_record(row, "exact normalized resource match") for row in object_rows]

    relevant: list[dict[str, Any]] = []
    seen: set[int] = set()
    # Exact-object events carry the strongest observable linkage.
    for row in object_rows[-limit:]:
        relevant.append(event_record(row, "same object"))
        seen.add(int(row["step_id"]))
    # Add recent events with the same operation family, then immediate context.
    same_family = []
    for row in prior:
        parsed = parse_capability(row.get("capability", ""))
        operation = parsed[0] if parsed else ""
        mapped = {
            "read": "observe", "write": "modify", "exec": "execute",
            "network": "external", "submit": "external", "delete": "irreversible",
        }.get(operation)
        if mapped == capability and int(row["step_id"]) not in seen:
            same_family.append(row)
    for row in same_family[-2:]:
        relevant.append(event_record(row, "same capability family"))
        seen.add(int(row["step_id"]))
    for row in prior[-3:]:
        if int(row["step_id"]) not in seen:
            relevant.append(event_record(row, "immediate predecessor"))
    relevant.sort(key=lambda item: item["step"])
    return relevant[-limit:], object_history


def alternatives(
    audit: dict[str, str], relevant: list[dict[str, Any]], object_history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate competing readings and cite only observable supporting facts."""
    relation = audit["original_relation"]
    capability = audit["capability"]
    evidence = audit.get("experiment_10_evidence", "")
    task = audit.get("task_objective", "")
    result: list[dict[str, Any]] = []

    if relation == "grounded":
        result.append({
            "interpretation": "explicit task grounding may authorize the action",
            "supporting_evidence": [evidence, f"task extract: {compact(task, 220)}"],
        })
    else:
        result.append({
            "interpretation": "the action may lack explicit task-level authorization",
            "supporting_evidence": [evidence, f"original relation: {relation}"],
        })

    if object_history:
        result.append({
            "interpretation": "prior work on the same object may imply workflow permission",
            "supporting_evidence": [
                f"{len(object_history)} earlier exact-object event(s)",
                *[f"step {item['step']}: {item['action']}" for item in object_history[-3:]],
            ],
        })
    else:
        result.append({
            "interpretation": "the object may be newly introduced at this action",
            "supporting_evidence": ["no earlier exact normalized-resource event was recovered"],
        })

    if capability in HIGH_IMPACT and relation != "grounded":
        result.append({
            "interpretation": "the action may require confirmation because impact is high and grounding is not explicit",
            "supporting_evidence": [f"capability: {capability}", f"original relation: {relation}"],
        })

    result.append({
        "interpretation": "the candidate may reflect taxonomy or parser undercoverage",
        "supporting_evidence": [
            "task relation was produced by lexical/object matching in Experiment 10",
            f"selection basis: {audit.get('selection_reason', '')}",
            f"recovered relevant prior events: {len(relevant)}",
        ],
    })
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=root / "results/authority_ambiguity_audit.csv")
    parser.add_argument("--steps", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--traces", type=Path, default=root.parent / "traces/public_swe_100")
    parser.add_argument("--output", type=Path, default=root / "results/authority_annotation_assistant.csv")
    args = parser.parse_args()

    audit_rows = read_csv(args.input)
    step_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.steps):
        step_rows[row["trace"]].append(row)
    for rows in step_rows.values():
        rows.sort(key=lambda row: int(row["step_id"]))

    objectives: dict[str, str] = {}
    output = []
    for audit in audit_rows:
        trace_name = audit["trace"]
        if trace_name not in step_rows:
            raise SystemExit(f"Missing step data for trace: {trace_name}")
        if trace_name not in objectives:
            prompt = initial_task(load_trace(args.traces / trace_name))
            objectives[trace_name] = objective_from_prompt(prompt)
        step = int(audit["step"])
        matching = [row for row in step_rows[trace_name] if int(row["step_id"]) == step]
        if len(matching) != 1:
            raise SystemExit(f"Expected one source event for {trace_name} step {step}; found {len(matching)}")
        resource = event_resource(matching[0])
        relevant, history = prior_context(
            step_rows[trace_name], step, resource, audit["capability"]
        )
        interpretations = alternatives(audit, relevant, history)
        output.append({
            "trace": trace_name,
            "step": step,
            "action": audit["action"],
            "capability": audit["capability"],
            "original_relation": audit["original_relation"],
            "task_summary": task_summary(objectives[trace_name]),
            "previous_relevant_events": json.dumps(relevant, ensure_ascii=False),
            "object_history": json.dumps(history, ensure_ascii=False),
            "possible_authority_interpretation": json.dumps(
                [item["interpretation"] for item in interpretations], ensure_ascii=False
            ),
            "evidence_supporting_each_interpretation": json.dumps(
                interpretations, ensure_ascii=False
            ),
        })

    if not output:
        raise SystemExit("No audit events found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps({
        "events": len(output),
        "traces": len({row["trace"] for row in output}),
        "category_assigned": False,
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
