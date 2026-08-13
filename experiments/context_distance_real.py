#!/usr/bin/env python3
"""Measure temporal distance to linked context in real SWE-Agent traces.

This experiment does not infer authorization, safety, intent, or security labels.
It measures only auditable temporal relations under explicit matching rules:

* delete: first prior create/write/object event for the same normalized resource;
* submit: first prior write to a path present in the trace's generated patch;
* external: prior introduction of the same URL/domain in the task or an action;
* package change: prior mention of an installed package in the task or an action.

Unmatched actions remain in the output with an empty distance. Summary rates use
matched relations as the denominator and report match coverage separately.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import urlparse


CAPABILITY = re.compile(r"^(?P<op>[^:]+):(?P<resource>.*)\((?P<effect>[^()]*)\)$")
URL = re.compile(r"https?://[^\s\"'<>`)]+", re.IGNORECASE)
PATCH_PATH = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
INSTALL_COMMAND = re.compile(r"(?:^|\s)(?:python\s+-m\s+)?(?:pip3?|uv)\s+install\b|(?:^|\s)(?:npm|yarn|pnpm)\s+(?:install|add)\b|(?:^|\s)(?:apt-get|apt)\s+install\b", re.IGNORECASE)
MANIFEST_NAMES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "package.json", "package-lock.json"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_capability(text: str) -> tuple[str, str] | None:
    match = CAPABILITY.match(text)
    return (match["op"], match["resource"]) if match else None


def normalize_resource(resource: str) -> str:
    value = resource.strip().strip("`\"'")
    while value.startswith("./"):
        value = value[2:]
    return value.rstrip("/")


def load_trace(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def initial_task(trace: dict[str, Any]) -> str:
    for message in trace.get("trajectory", []):
        if isinstance(message, dict) and str(message.get("role", "")).lower() == "user":
            text = message.get("text")
            return text if isinstance(text, str) else ""
    return ""


def patch_paths(trace: dict[str, Any]) -> set[str]:
    patch = trace.get("generated_patch", "")
    if not isinstance(patch, str):
        return set()
    paths = set()
    for left, right in PATCH_PATH.findall(patch):
        for path in (left, right):
            if path != "/dev/null":
                paths.add(normalize_resource(path))
    return paths


def urls(text: str) -> list[str]:
    return [value.rstrip(".,;:]") for value in URL.findall(text)]


def url_keys(text: str) -> set[str]:
    keys = set()
    for value in urls(text):
        keys.add(value.lower())
        host = (urlparse(value).hostname or "").lower()
        if host:
            keys.add(host)
    return keys


def tokenize(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def package_tokens(action: str) -> list[str]:
    tokens = tokenize(action)
    lower = [token.lower() for token in tokens]
    start = None
    for index, token in enumerate(lower):
        if token in {"pip", "pip3", "uv", "npm", "yarn", "pnpm", "apt", "apt-get"}:
            for offset in range(index + 1, min(index + 3, len(tokens))):
                if lower[offset] in {"install", "add"}:
                    start = offset + 1
                    break
        if start is not None:
            break
    if start is None:
        return []
    packages = []
    for token in tokens[start:]:
        if token.startswith("-") or token in {"&&", "|", ";"}:
            continue
        value = re.split(r"[<>=!~@\[]", token, maxsplit=1)[0].strip("'\"")
        if value and "/" not in value and not value.startswith("."):
            packages.append(value.lower())
    return packages


def token_present(text: str, token: str) -> bool:
    variants = {token.lower(), token.lower().replace("-", "_"), token.lower().replace("_", "-")}
    lowered = text.lower()
    return any(re.search(rf"(?<![a-z0-9_.-]){re.escape(value)}(?![a-z0-9_.-])", lowered) for value in variants)


def classify(row: dict[str, str]) -> str | None:
    parsed = parse_capability(row["capability"])
    operation = parsed[0] if parsed else ""
    action = row["args_first_line"]
    if operation == "delete" or action.lstrip().startswith("rm "):
        return "delete"
    if operation == "submit" or row["tool"] == "submit":
        return "submit"
    if operation == "network":
        return "external"
    if INSTALL_COMMAND.search(action) or (operation == "write" and parsed and parsed[1] == "@site-packages"):
        return "package_change"
    return None


def make_context(step: int, context_type: str, action: str, rule: str) -> dict[str, Any]:
    return {"step": step, "type": context_type, "action": action, "rule": rule}


def match_delete(action_row: dict[str, str], prior: list[dict[str, str]]) -> tuple[str, dict[str, Any] | None]:
    parsed = parse_capability(action_row["capability"])
    target = normalize_resource(parsed[1]) if parsed else ""
    candidates = []
    for row in prior:
        prior_capability = parse_capability(row["capability"])
        if prior_capability is None or normalize_resource(prior_capability[1]) != target:
            continue
        op = prior_capability[0]
        if op == "write" and row["tool"] == "create_file":
            priority, context_type = 0, "create"
        elif op == "write":
            priority, context_type = 1, "prior_write"
        else:
            priority, context_type = 2, "object_introduction"
        candidates.append((priority, int(row["step_id"]), context_type, row))
    if not candidates:
        return target, None
    # Prefer explicit creation, then any write, then other exact-resource events;
    # within a class choose the earliest introduction to measure its full horizon.
    priority, step, context_type, row = min(candidates, key=lambda value: (value[0], value[1]))
    del priority
    return target, make_context(step, context_type, row["args_first_line"], "exact_normalized_resource_identity")


def match_submit(action_row: dict[str, str], prior: list[dict[str, str]], changed_paths: set[str]) -> tuple[str, dict[str, Any] | None]:
    candidates = []
    for row in prior:
        parsed = parse_capability(row["capability"])
        if parsed and parsed[0] == "write" and normalize_resource(parsed[1]) in changed_paths:
            candidates.append(row)
    if not candidates:
        return "@submission", None
    row = min(candidates, key=lambda value: int(value["step_id"]))
    parsed = parse_capability(row["capability"])
    path = normalize_resource(parsed[1]) if parsed else ""
    return "@submission", make_context(int(row["step_id"]), "submitted_object_introduction", row["args_first_line"], f"first_write_to_generated_patch_path:{path}")


def match_external(action_row: dict[str, str], prior: list[dict[str, str]], task: str) -> tuple[str, dict[str, Any] | None]:
    action_keys = url_keys(action_row["args_first_line"])
    target = sorted(action_keys, key=len, reverse=True)[0] if action_keys else ""
    shared_task_keys = action_keys & url_keys(task)
    if shared_task_keys:
        key = sorted(shared_task_keys, key=len, reverse=True)[0]
        return target, make_context(0, "task_object_introduction", key, "same_url_or_domain_in_initial_task")
    for row in prior:
        shared = action_keys & url_keys(row["args_first_line"])
        if shared:
            key = sorted(shared, key=len, reverse=True)[0]
            return target, make_context(int(row["step_id"]), "object_introduction", row["args_first_line"], f"same_url_or_domain:{key}")
    return target, None


def match_package(action_row: dict[str, str], prior: list[dict[str, str]], task: str) -> tuple[str, dict[str, Any] | None]:
    packages = package_tokens(action_row["args_first_line"])
    target = "|".join(packages)
    for package in packages:
        if token_present(task, package):
            return target, make_context(0, "task_object_introduction", package, f"same_package_token_in_initial_task:{package}")
    for row in prior:
        for package in packages:
            if token_present(row["args_first_line"], package):
                return target, make_context(int(row["step_id"]), "object_introduction", row["args_first_line"], f"same_package_token:{package}")
    # Manifest reads are retained as a separate, weaker structural relation and
    # never claimed to introduce a particular package.
    manifest_rows = []
    for row in prior:
        parsed = parse_capability(row["capability"])
        if parsed and Path(normalize_resource(parsed[1])).name.lower() in MANIFEST_NAMES:
            manifest_rows.append(row)
    if manifest_rows:
        row = min(manifest_rows, key=lambda value: int(value["step_id"]))
        return target, make_context(int(row["step_id"]), "dependency_manifest_introduction", row["args_first_line"], "prior_dependency_manifest_event_no_package_identity_claim")
    return target, None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"denominator_note": "Threshold percentages use matched context relations only."}
    examples = []
    for family in ["all", "delete", "submit", "external", "package_change"]:
        subset = rows if family == "all" else [row for row in rows if row["action_family"] == family]
        matched = [row for row in subset if row["context_found"]]
        distances = [int(row["context_distance"]) for row in matched]
        bins = Counter()
        for distance in distances:
            if distance <= 5:
                bins["0-5"] += 1
            elif distance <= 10:
                bins["6-10"] += 1
            elif distance <= 20:
                bins["11-20"] += 1
            else:
                bins[">20"] += 1
        total = len(distances)
        result[family] = {
            "actions": len(subset),
            "matched": total,
            "match_rate": round(total / len(subset), 4) if subset else None,
            "distance_distribution": {key: bins[key] for key in ("0-5", "6-10", "11-20", ">20")},
            "median": median(distances) if distances else None,
            "max": max(distances) if distances else None,
            "percentage_gt5": round(100 * sum(value > 5 for value in distances) / total, 2) if total else None,
            "percentage_gt10": round(100 * sum(value > 10 for value in distances) / total, 2) if total else None,
            "percentage_gt20": round(100 * sum(value > 20 for value in distances) / total, 2) if total else None,
        }
    for row in sorted((row for row in rows if row["context_found"]), key=lambda value: int(value["context_distance"]), reverse=True)[:12]:
        examples.append({key: row[key] for key in ("trace", "action_family", "action_step", "action", "context_step", "context_distance", "context_type", "context_action", "match_rule")})
    result["long_horizon_examples"] = examples
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--traces", type=Path, default=root.parent / "traces/public_swe_100")
    parser.add_argument("--output", type=Path, default=root / "results/context_distance_real.csv")
    parser.add_argument("--summary", type=Path, default=root / "results/context_distance_real_summary.json")
    args = parser.parse_args()

    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.steps):
        by_trace[row["trace"]].append(row)

    output = []
    for trace_name, trace_rows in sorted(by_trace.items()):
        trace_rows.sort(key=lambda row: int(row["step_id"]))
        trace = load_trace(args.traces / trace_name)
        task = initial_task(trace)
        changed_paths = patch_paths(trace)
        for index, row in enumerate(trace_rows):
            family = classify(row)
            if family is None:
                continue
            prior = trace_rows[:index]
            if family == "delete":
                target, context = match_delete(row, prior)
            elif family == "submit":
                target, context = match_submit(row, prior, changed_paths)
            elif family == "external":
                target, context = match_external(row, prior, task)
            else:
                target, context = match_package(row, prior, task)
            action_step = int(row["step_id"])
            distance = action_step - int(context["step"]) if context else None
            output.append(
                {
                    "trace": trace_name,
                    "action_family": family,
                    "action_step": action_step,
                    "action": row["args_first_line"],
                    "capability": row["capability"],
                    "target": target,
                    "context_found": context is not None,
                    "context_step": context["step"] if context else "",
                    "context_distance": distance if distance is not None else "",
                    "context_type": context["type"] if context else "",
                    "context_action": context["action"] if context else "",
                    "match_rule": context["rule"] if context else "unmatched",
                    "requires_gt5": distance > 5 if distance is not None else "",
                    "requires_gt10": distance > 10 if distance is not None else "",
                    "requires_gt20": distance > 20 if distance is not None else "",
                }
            )

    if not output:
        raise SystemExit("No high-impact actions found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    summary = summarize(output)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "long_horizon_examples"}, indent=2))
    print(f"saved: {args.output}")
    print(f"saved: {args.summary}")


if __name__ == "__main__":
    main()
