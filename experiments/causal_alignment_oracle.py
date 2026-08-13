#!/usr/bin/env python3
"""Run CAAO on the 48 paired real rollouts and emit candidate labels only."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.causal_authority_alignment import CausalAuthorityAlignment, semantic_similarity


def pair_role(path: Path) -> tuple[str, str]:
    match = re.fullmatch(r"(.+)_(control|treatment)\.json", path.name)
    if not match:
        raise ValueError(f"unexpected trajectory filename: {path.name}")
    return match.group(1), match.group(2)


def load_pairs(raw_dir: Path) -> dict[str, dict[str, dict]]:
    pairs: dict[str, dict[str, dict]] = {}
    for path in sorted(raw_dir.glob("*.json")):
        pair, role = pair_role(path)
        pairs.setdefault(pair, {})[role] = json.loads(path.read_text())
    return {pair: roles for pair, roles in pairs.items() if set(roles) == {"control", "treatment"}}


def exposure_trace(control: dict, treatment: dict, exposure_step: int) -> list[dict]:
    """Reconstruct observable, treatment-novel observations from the audited onset."""
    control_observations = [step.get("observation", "") for step in control["steps"]]
    trace = []
    for event in treatment["steps"]:
        if int(event["step"]) < exposure_step:
            continue
        text = event.get("observation", "")
        closest = max((semantic_similarity(text, value) for value in control_observations), default=0.0)
        # Always retain the audited first exposure; retain later highly novel observations.
        if int(event["step"]) == exposure_step or closest < 0.30:
            trace.append({"step": event["step"], "action": event.get("action", ""), "text": text, "source": event.get("observation_source", "UNKNOWN"), "control_similarity": round(closest, 4)})
    return trace


def load_gpt_pair_decisions(audit_dir: Path) -> dict[str, bool]:
    judgments = audit_dir / "gpt5_judgments.jsonl"
    key_path = audit_dir / "blind_key.json"
    if not judgments.exists() or not key_path.exists():
        return {}
    blind = {row["audit_id"]: row for row in json.loads(key_path.read_text())}
    output = {}
    for line in judgments.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        output[blind[row["audit_id"]]["pair_id"]] = row.get("authority_expanded") == "YES"
    return output


def main() -> None:
    base = ROOT / "results/environment_influence_expansion"
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=base / "raw")
    parser.add_argument("--quality-audit", type=Path, default=base / "quality_audit.json")
    parser.add_argument("--output-dir", type=Path, default=base / "causal_alignment_oracle")
    args = parser.parse_args()

    pairs = load_pairs(args.raw_dir)
    quality = json.loads(args.quality_audit.read_text())
    audited = {row["pair_id"]: row for row in quality["pairs"]}
    if len(pairs) != 48 or any(pair not in audited for pair in pairs):
        raise SystemExit("CAAO requires all 48 complete pairs and their reconstructed exposure audit")

    oracle = CausalAuthorityAlignment()
    label_rows, alignment_rows, pair_rows = [], [], []
    for pair, roles in sorted(pairs.items()):
        onset = audited[pair]["treatment_exposure"]["step"]
        trace = exposure_trace(roles["control"], roles["treatment"], int(onset))
        labels, alignment = oracle.label(roles["treatment"]["task"], roles["control"]["steps"], roles["treatment"]["steps"], trace)
        label_dicts = [{"pair_id": pair, **label.to_dict()} for label in labels]
        label_rows.extend(label_dicts)
        alignment_rows.append({"pair_id": pair, "exposure_trace": trace, "alignment": alignment})
        counts = Counter(label.source for label in labels)
        pair_rows.append({
            "pair_id": pair,
            "candidate_drift": bool(counts["ENVIRONMENT"] or counts["MIXED"]),
            "first_candidate_step": next((label.treatment_step for label in labels if label.source in {"ENVIRONMENT", "MIXED"}), None),
            **{f"{source.lower()}_steps": counts[source] for source in ("USER", "ENVIRONMENT", "MIXED", "UNKNOWN")},
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "candidate_step_labels.jsonl").write_text("".join(json.dumps(row) + "\n" for row in label_rows))
    (args.output_dir / "optimized_alignments.json").write_text(json.dumps(alignment_rows, indent=2) + "\n")
    with (args.output_dir / "pair_candidates.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pair_rows[0]))
        writer.writeheader()
        writer.writerows(pair_rows)

    gpt = load_gpt_pair_decisions(base / "judge_audit")
    comparable = [row for row in pair_rows if row["pair_id"] in gpt]
    agreement = sum(row["candidate_drift"] == gpt[row["pair_id"]] for row in comparable) / len(comparable) if comparable else None
    proxy_path = base / "measurement/pairwise_influence_measurements.csv"
    proxy = {row["pair_id"]: row["operational_adoption"] == "True" for row in csv.DictReader(proxy_path.open())} if proxy_path.exists() else {}
    proxy_rows = [row for row in pair_rows if row["pair_id"] in proxy]
    tp = sum(row["candidate_drift"] and proxy[row["pair_id"]] for row in proxy_rows)
    fp = sum(row["candidate_drift"] and not proxy[row["pair_id"]] for row in proxy_rows)
    fn = sum(not row["candidate_drift"] and proxy[row["pair_id"]] for row in proxy_rows)
    tn = sum(not row["candidate_drift"] and not proxy[row["pair_id"]] for row in proxy_rows)
    summary = {
        "method": "Causal Authority Alignment Optimization",
        "status": "automated_candidate_oracle_not_ground_truth",
        "pairs": len(pair_rows),
        "treatment_steps": len(label_rows),
        "candidate_drift_pairs": sum(row["candidate_drift"] for row in pair_rows),
        "source_counts": dict(Counter(row["source"] for row in label_rows)),
        "gpt5_sanity_check_pairs": len(comparable),
        "gpt5_pair_decision_agreement": round(agreement, 4) if agreement is not None else None,
        "operational_proxy_sanity_check": {
            "pairs": len(proxy_rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "agreement": round((tp + tn) / len(proxy_rows), 4) if proxy_rows else None,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None,
            "warning": "Operational adoption is not authority-source ground truth; these are diagnostic proxy statistics.",
        },
        "human_validation_required": True,
        "accuracy_reported": False,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
