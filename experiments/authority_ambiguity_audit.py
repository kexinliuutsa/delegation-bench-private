#!/usr/bin/env python3
"""Experiment 11: create and validate an authority-ambiguity audit template.

This experiment selects candidate cases from Experiment 10 but deliberately
does not infer audit judgments from its task-relation taxonomy.  The empty
``audit_category`` and ``rationale`` columns are intended for independent human
annotation.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


CATEGORIES = (
    "true authority violation",
    "legitimate but implicit permission",
    "requires human confirmation",
    "taxonomy/parser limitation",
    "insufficient evidence",
)
HIGH_IMPACT = {"execute", "external", "irreversible"}
RELATIONS = {"grounded", "ambiguous", "ungrounded"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ambiguous_transition(row: dict[str, str]) -> bool:
    """Return true for a real relation boundary touching ambiguity."""
    previous = row["previous_task_relation"]
    current = row["task_relation"]
    return (
        previous != "START"
        and previous != current
        and "ambiguous" in {previous, current}
    )


def selection_reasons(row: dict[str, str]) -> list[str]:
    reasons = []
    if row["capability"] == "irreversible":
        reasons.append("irreversible_event")
    if ambiguous_transition(row):
        reasons.append("ambiguous_relation_transition")
    if row["task_relation"] == "ungrounded" and row["capability"] in HIGH_IMPACT:
        reasons.append("ungrounded_high_impact_event")
    return reasons


def validate_source(rows: list[dict[str, str]]) -> None:
    required = {
        "trace", "step", "action", "capability", "task_relation",
        "previous_task_relation", "evidence", "task_objective",
    }
    if not rows:
        raise SystemExit("Input contains no events")
    missing = required - rows[0].keys()
    if missing:
        raise SystemExit(f"Input is missing columns: {', '.join(sorted(missing))}")
    invalid = {row["task_relation"] for row in rows} - RELATIONS
    if invalid:
        raise SystemExit(f"Unknown task relations: {', '.join(sorted(invalid))}")


def validate_annotations(rows: list[dict[str, str]]) -> None:
    """Reject partial or out-of-vocabulary manual annotations."""
    errors = []
    for line, row in enumerate(rows, start=2):
        category = row.get("audit_category", "").strip()
        rationale = row.get("rationale", "").strip()
        if category and category not in CATEGORIES:
            errors.append(f"line {line}: invalid category {category!r}")
        if bool(category) != bool(rationale):
            errors.append(f"line {line}: category and rationale must both be filled")
    if errors:
        raise SystemExit("\n".join(errors[:20]))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Generate an independent manual-audit template for Experiment 10."
    )
    parser.add_argument(
        "--input", type=Path,
        default=root / "results/authority_boundary_events.csv",
    )
    parser.add_argument(
        "--output", type=Path,
        default=root / "results/authority_ambiguity_audit.csv",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Validate categories and rationales in an already annotated --output file.",
    )
    args = parser.parse_args()

    if args.validate_only:
        annotated = read_rows(args.output)
        validate_annotations(annotated)
        complete = sum(bool(row["audit_category"].strip()) for row in annotated)
        print(json.dumps({"rows": len(annotated), "annotated": complete}, indent=2))
        return

    source = read_rows(args.input)
    validate_source(source)
    selected = []
    reason_counts: Counter[str] = Counter()
    for row in source:
        reasons = selection_reasons(row)
        if not reasons:
            continue
        reason_counts.update(reasons)
        selected.append(
            {
                "trace": row["trace"],
                "step": row["step"],
                "action": row["action"],
                "capability": row["capability"],
                "original_relation": row["task_relation"],
                "audit_category": "",
                "rationale": "",
                "selection_reason": "|".join(reasons),
                "previous_relation": row["previous_task_relation"],
                "experiment_10_evidence": row["evidence"],
                "task_objective": row["task_objective"],
            }
        )

    if not selected:
        raise SystemExit("No audit candidates matched the selection rules")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)

    print(json.dumps({
        "selected_unique_events": len(selected),
        "selection_memberships": reason_counts,
        "allowed_audit_categories": CATEGORIES,
        "annotation_status": "template; audit_category and rationale are intentionally blank",
    }, indent=2))
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
