#!/usr/bin/env python3
"""Experiment 51: execute real environmental-influence rollouts only."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def normalize(raw: dict, job: dict, model: str) -> dict:
    events = raw.get("steps", raw.get("trajectory", []))
    steps = []
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict):
            continue
        action = event.get("action", event.get("command", ""))
        if not action:
            continue
        steps.append({
            "step": index,
            "tool": event.get("tool", "unknown"),
            "action": action,
            "observation": event.get("observation", event.get("output", "")),
            "observation_source": event.get("observation_source", event.get("source_channel", "UNKNOWN")),
        })
    if not steps:
        raise ValueError("real runner produced no actions")
    return {"task": job["task"], "seed": job["seed"], "model": model, "steps": steps}


def valid_existing(path: Path, job: dict, model: str) -> bool:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return set(value) == {"task", "seed", "model", "steps"} and value["task"] == job["task"] and value["seed"] == job["seed"] and value["model"] == model and bool(value["steps"])


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    base = root / "results/environment_influence_expansion"
    parser.add_argument("--manifest", type=Path, default=base / "collection_manifest.json")
    parser.add_argument("--output-dir", type=Path, default=base)
    parser.add_argument("--model", required=True)
    parser.add_argument("--native-command", required=True, help="Template using only {task}, {repo}, {seed}, {model}, {output}")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="Isolated rollout workers (1-8)")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("real rollout execution requires --execute")
    forbidden_placeholders = ("{pair_id}", "{condition}", "{injection", "{environment", "{experiment", "{influence")
    if any(value in args.native_command.lower() for value in forbidden_placeholders):
        raise SystemExit("native command exposes forbidden experimental metadata")
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")

    manifest = json.loads(args.manifest.read_text())
    jobs = manifest.get("jobs", [])
    if manifest.get("pair_count") != 48 or len(jobs) != 96:
        raise SystemExit(f"expected fixed Experiment 51 protocol of 48 pairs/96 jobs, got {manifest.get('pair_count')}/{len(jobs)}")
    raw_dir = args.output_dir / "raw"
    failure_dir = args.output_dir / "failures"
    workspace_dir = args.output_dir / "rollout_workspaces"
    for path in (raw_dir, failure_dir, workspace_dir):
        path.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        existing = list(raw_dir.glob("*.json"))
        if existing:
            raise SystemExit("raw trajectories already exist; use --resume to preserve real data")

    def run_job(job: dict) -> dict:
        destination = raw_dir / f"{job['pair_id']}_{job['condition']}.json"
        if args.resume and destination.exists() and valid_existing(destination, job, args.model):
            return {"pair_id": job["pair_id"], "condition": job["condition"], "status": "COMPLETE", "trajectory": str(destination), "resumed": True}
        source = Path(job["repository"])
        workspace = Path(tempfile.mkdtemp(prefix="e51_", dir=workspace_dir))
        repository = workspace / "repo"
        shutil.copytree(source, repository)
        native_output = workspace / "native.json"
        command = args.native_command.format(task=shlex.quote(job["task"]), repo=shlex.quote(str(repository)), seed=job["seed"], model=shlex.quote(args.model), output=shlex.quote(str(native_output)))
        completed = subprocess.run(command, shell=True, cwd=root, text=True, capture_output=True)
        stderr = failure_dir / f"{job['pair_id']}_{job['condition']}.stderr"
        stderr.write_text(completed.stderr)
        record = {"pair_id": job["pair_id"], "condition": job["condition"], "status": "FAILED", "stderr": str(stderr)}
        try:
            if completed.returncode:
                raise RuntimeError(f"native runner exit {completed.returncode}")
            if not native_output.exists():
                raise RuntimeError("native runner produced no output")
            trajectory = normalize(json.loads(native_output.read_text()), job, args.model)
            destination.write_text(json.dumps(trajectory, indent=2) + "\n")
            record.update(status="COMPLETE", trajectory=str(destination))
        except Exception as error:
            record["error"] = str(error)
        return record

    if args.workers == 1:
        records = [run_job(job) for job in jobs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            records = list(executor.map(run_job, jobs))

    complete = sum(x["status"] == "COMPLETE" for x in records)
    pair_ids = {job["pair_id"] for job in jobs}
    completed_pairs = sum(all(any(x["pair_id"] == pair_id and x["condition"] == condition and x["status"] == "COMPLETE" for x in records) for condition in ("control", "treatment")) for pair_id in pair_ids)
    status = {"model": args.model, "expected_trajectories": 96, "completed_trajectories": complete, "completed_pairs": completed_pairs, "labels_generated": False, "oracle_used": False, "jobs": records}
    (args.output_dir / "rollout_status.json").write_text(json.dumps(status, indent=2) + "\n")
    audit_command = [sys.executable, str(root / "experiments/environment_rollout_quality_audit.py"), "--manifest", str(args.manifest), "--raw-dir", str(raw_dir), "--output", str(args.output_dir / "quality_audit.json")]
    subprocess.run(audit_command, check=True)
    print(json.dumps({"completed_trajectories": complete, "failed_trajectories": len(records) - complete, "completed_pairs": completed_pairs, "labels_generated": False, "oracle_used": False}, indent=2))


if __name__ == "__main__":
    main()
