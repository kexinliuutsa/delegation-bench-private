#!/usr/bin/env python3
"""Quality audit for Experiment 51 real paired rollouts.

Exposure is reconstructed from treatment-only repository bytes appearing in
recorded observations. Manifest descriptions are never accepted as exposure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


FORBIDDEN_INPUT_TERMS = ("injection style", "pair id", "condition")
PROMPT_FIELDS = ("task", "system_prompt", "prompt", "messages", "input_messages")


def load_trajectory(path: Path) -> dict:
    value = json.loads(path.read_text())
    required = {"task", "seed", "model", "steps"}
    if set(value) != required:
        raise ValueError(f"{path}: trajectory fields must be exactly {sorted(required)}")
    if not value["steps"]:
        raise ValueError(f"{path}: empty trajectory")
    for index, event in enumerate(value["steps"], 1):
        if set(event) != {"step", "tool", "action", "observation", "observation_source"}:
            raise ValueError(f"{path}: invalid fields at step {index}")
        if event["step"] != index or not event["action"]:
            raise ValueError(f"{path}: invalid step sequence/action at step {index}")
    return value


def differing_fragments(control: Path, treatment: Path) -> tuple[list[str], list[str]]:
    names = sorted(
        {p.relative_to(control).as_posix() for p in control.rglob("*") if p.is_file()}
        | {p.relative_to(treatment).as_posix() for p in treatment.rglob("*") if p.is_file()}
    )
    changed, fragments = [], []
    for name in names:
        left_path, right_path = control / name, treatment / name
        left = set(left_path.read_text(errors="replace").splitlines()) if left_path.is_file() else set()
        right = set(right_path.read_text(errors="replace").splitlines()) if right_path.is_file() else set()
        if left != right:
            changed.append(name)
            fragments.extend(line.strip().lower() for line in right - left if len(line.strip()) >= 8)
    return changed, sorted(set(fragments), key=lambda x: (-len(x), x))


def reconstruct_exposure(trajectory: dict, fragments: list[str]) -> dict:
    for event in trajectory["steps"]:
        observation = str(event["observation"]).lower()
        matched = next((fragment for fragment in fragments if fragment in observation), None)
        if matched:
            return {
                "visible": True,
                "step": event["step"],
                "observation_source": event["observation_source"],
                "evidence_sha256": hashlib.sha256(matched.encode()).hexdigest(),
            }
    return {"visible": False, "step": None, "observation_source": None, "evidence_sha256": None}


def leakage_audit(trajectory: dict) -> dict:
    values = []
    audited = []
    for field in PROMPT_FIELDS:
        if field in trajectory:
            audited.append(field)
            value = trajectory[field]
            values.append(value if isinstance(value, str) else json.dumps(value, sort_keys=True))
    text = "\n".join(values).lower()
    matches = [term for term in FORBIDDEN_INPUT_TERMS if re.search(rf"\b{re.escape(term)}\b", text)]
    return {"leakage": bool(matches), "matched_terms": matches, "audited_fields": audited}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    base = root / "results/environment_influence_expansion"
    parser.add_argument("--manifest", type=Path, default=base / "collection_manifest.json")
    parser.add_argument("--raw-dir", type=Path, default=base / "raw")
    parser.add_argument("--output", type=Path, default=base / "quality_audit.json")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    grouped = {}
    for job in manifest["jobs"]:
        grouped.setdefault(job["pair_id"], {})[job["condition"]] = job
    pair_results = []
    for pair_id, jobs in sorted(grouped.items()):
        paths = {condition: args.raw_dir / f"{pair_id}_{condition}.json" for condition in ("control", "treatment")}
        trajectories, errors = {}, []
        for condition, path in paths.items():
            if not path.exists():
                errors.append(f"missing_{condition}")
                continue
            try:
                trajectories[condition] = load_trajectory(path)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"invalid_{condition}: {error}")
        complete = set(trajectories) == {"control", "treatment"}
        changed, fragments = differing_fragments(Path(jobs["control"]["repository"]), Path(jobs["treatment"]["repository"]))
        exposure = {condition: reconstruct_exposure(value, fragments) for condition, value in trajectories.items()}
        leakage = {condition: leakage_audit(value) for condition, value in trajectories.items()}
        pair_results.append({
            "pair_id": pair_id,
            "task_id": jobs["control"]["task_id"],
            "injection_level": jobs["control"]["injection_level"],
            "pair_complete": complete,
            "errors": errors,
            "reconstructed_difference_files": changed,
            "treatment_exposure": exposure.get("treatment", {"visible": False, "step": None, "observation_source": None, "evidence_sha256": None}),
            "control_exposure": exposure.get("control", {"visible": False, "step": None, "observation_source": None, "evidence_sha256": None}),
            "prompt_leakage": leakage,
            "thought_fields_absent": complete and all("thought" not in json.dumps(value).lower() and "reasoning" not in json.dumps(value).lower() for value in trajectories.values()),
        })
    report = {
        "schema_version": "environment-rollout-quality-v1",
        "expected_pairs": 48,
        "complete_pairs": sum(x["pair_complete"] for x in pair_results),
        "treatment_exposures_reconstructed": sum(x["treatment_exposure"]["visible"] for x in pair_results),
        "control_exposure_false_positives": sum(x["control_exposure"]["visible"] for x in pair_results),
        "prompt_leakage_count": sum(any(v["leakage"] for v in x["prompt_leakage"].values()) for x in pair_results),
        "labels_generated": False,
        "oracle_used": False,
        "pairs": pair_results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("expected_pairs", "complete_pairs", "treatment_exposures_reconstructed", "control_exposure_false_positives", "prompt_leakage_count", "labels_generated", "oracle_used")}, indent=2))


if __name__ == "__main__":
    main()

