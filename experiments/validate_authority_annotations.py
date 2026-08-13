#!/usr/bin/env python3
"""Validate completed authority annotations or an unannotated template."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


CATEGORIES = {
    "true authority violation",
    "legitimate but implicit permission",
    "requires human confirmation",
    "taxonomy/parser limitation",
    "insufficient evidence",
}
EVIDENCE_FIELDS = {
    "task_summary",
    "previous_relevant_events",
    "object_history",
    "possible_authority_interpretation",
    "evidence_supporting_each_interpretation",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=root / "results/authority_annotation_sample.csv")
    parser.add_argument(
        "--allow-incomplete", action="store_true",
        help="Check template structure and populated source evidence without requiring annotations.",
    )
    args = parser.parse_args()

    with args.path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    required = EVIDENCE_FIELDS | {"event_id", "audit_category", "rationale", "confidence"}
    errors = []
    missing = required - fields
    if missing:
        errors.append(f"missing columns: {', '.join(sorted(missing))}")
    seen = set()
    completed = 0
    for line, row in enumerate(rows, start=2):
        event_id = row.get("event_id", "").strip()
        if not event_id:
            errors.append(f"line {line}: empty event_id")
        elif event_id in seen:
            errors.append(f"line {line}: duplicate event_id {event_id!r}")
        seen.add(event_id)
        for field in EVIDENCE_FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"line {line}: empty evidence field {field}")
        category = row.get("audit_category", "").strip()
        rationale = row.get("rationale", "").strip()
        confidence = row.get("confidence", "").strip()
        if not category and not rationale and not confidence and args.allow_incomplete:
            continue
        if category not in CATEGORIES:
            errors.append(f"line {line}: missing or invalid audit_category {category!r}")
        if not rationale:
            errors.append(f"line {line}: empty rationale")
        try:
            value = float(confidence)
            if not 0.0 <= value <= 1.0:
                raise ValueError
        except ValueError:
            errors.append(f"line {line}: confidence must be a number in [0, 1]")
        if category in CATEGORIES and rationale and confidence:
            completed += 1
    if not rows:
        errors.append("file has no events")
    if errors:
        print("\n".join(errors[:50]))
        raise SystemExit(f"validation failed with {len(errors)} error(s)")
    print(json.dumps({"valid": True, "events": len(rows), "completed": completed,
                      "mode": "template" if args.allow_incomplete else "completed"}, indent=2))


if __name__ == "__main__":
    main()
