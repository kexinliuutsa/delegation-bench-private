#!/usr/bin/env python3
"""Build a reproducible, unlabeled sample for manual authority annotation."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=root / "results/authority_annotation_assistant.csv")
    parser.add_argument("--output", type=Path, default=root / "results/authority_annotation_sample.csv")
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument(
        "--ambiguous-count", type=int, default=None,
        help="Number of non-irreversible ambiguous events; defaults to the irreversible count.",
    )
    args = parser.parse_args()

    rows = read_csv(args.input)
    irreversible = [row for row in rows if row["capability"] == "irreversible"]
    ambiguous_pool = [
        row for row in rows
        if row["original_relation"] == "ambiguous" and row["capability"] != "irreversible"
    ]
    count = len(irreversible) if args.ambiguous_count is None else args.ambiguous_count
    if count < 0 or count > len(ambiguous_pool):
        raise SystemExit(f"ambiguous count must be between 0 and {len(ambiguous_pool)}")
    sampled = random.Random(args.seed).sample(ambiguous_pool, count)

    selected = [(row, "all_irreversible") for row in irreversible]
    selected += [(row, "random_ambiguous") for row in sampled]
    selected.sort(key=lambda item: (item[0]["trace"], int(item[0]["step"])))

    output = []
    for row, stratum in selected:
        output.append({
            "event_id": f"{row['trace']}::step-{row['step']}",
            "sampling_stratum": stratum,
            **row,
            "audit_category": "",
            "rationale": "",
            "confidence": "",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps({
        "rows": len(output), "irreversible": len(irreversible),
        "random_ambiguous": len(sampled), "seed": args.seed,
        "labels_assigned": False, "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
