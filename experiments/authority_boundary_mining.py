#!/usr/bin/env python3
"""Experiment 10: mine task-relation boundaries in SWE-Agent trajectories.

No existing risk, DAR, grounding, or authorization labels are read. Capability
is derived from observable operation semantics; task relation is derived from
explicit task text evidence. `ungrounded` means no task-text support was found,
not that an action was unsafe or unauthorized.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from context_distance_real import initial_task, load_trace, normalize_resource, parse_capability, url_keys


OBSERVE = re.compile(r"\b(?:inspect|investigate|diagnos\w*|analy[sz]e|debug|find|identify|examine|review|reproduce)\b", re.IGNORECASE)
MODIFY = re.compile(r"\b(?:fix\w*|implement\w*|add\w*|chang\w*|updat\w*|correct\w*|support\w*|replac\w*|remov\w*|refactor\w*|modif\w*|patch\w*|creat\w*)\b", re.IGNORECASE)
EXECUTE = re.compile(r"\b(?:run|execute|test|verify|reproduce|invoke|launch)\b", re.IGNORECASE)
EXTERNAL = re.compile(r"\b(?:download|fetch|access|open|visit|query|search|upload|send|submit)\b", re.IGNORECASE)
IRREVERSIBLE = re.compile(r"\b(?:delet\w*|remov\w*|clean\s*up|cleanup|eras\w*|destroy\w*)\b", re.IGNORECASE)
ISSUE = re.compile(r"\b(?:bug|error|fail\w*|incorrect|wrong|issue|expected|actual|traceback|exception)\b", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def objective_from_prompt(prompt: str) -> str:
    match = re.search(r"ISSUE:\s*(.*?)(?:\n\s*INSTRUCTIONS:|\Z)", prompt, flags=re.IGNORECASE | re.DOTALL)
    objective = match.group(1) if match else prompt
    return objective.strip()


def capability_from_row(row: dict[str, str]) -> str | None:
    """Map observable operations; ignore encoded reversibility/risk suffixes."""
    parsed = parse_capability(row["capability"])
    if parsed is None:
        return None
    operation, _ = parsed
    if operation == "read":
        return "observe"
    if operation == "write":
        return "modify"
    if operation == "exec":
        return "execute"
    if operation in {"network", "submit"}:
        return "external"
    if operation == "delete":
        return "irreversible"
    return None


def resource_from_row(row: dict[str, str]) -> str:
    parsed = parse_capability(row["capability"])
    return normalize_resource(parsed[1]) if parsed else ""


def object_mentioned(objective: str, resource: str) -> bool:
    if not resource or resource.startswith("@"):
        return False
    lowered = objective.lower()
    variants = {resource.lower(), Path(resource).name.lower()}
    return any(value and value in lowered for value in variants)


def matching_external_evidence(objective: str, action: str) -> tuple[bool, str]:
    objective_keys = url_keys(objective)
    action_keys = url_keys(action)
    shared = objective_keys & action_keys
    if shared:
        key = sorted(shared, key=len, reverse=True)[0]
        return True, key
    # Capability normalization may retain a URL even when shell parsing is weak.
    for key in action_keys:
        host = (urlparse(key).hostname or "").lower() if key.startswith("http") else key
        if host and host in objective.lower():
            return True, host
    return False, ""


def relation_for_event(
    capability: str,
    row: dict[str, str],
    objective: str,
) -> tuple[str, str, float]:
    resource = resource_from_row(row)
    mentioned = object_mentioned(objective, resource)
    action = row["args_first_line"]

    if capability == "observe":
        if OBSERVE.search(objective) and mentioned:
            return "grounded", f"task explicitly requests observation and names object `{resource}`", 0.95
        if OBSERVE.search(objective):
            evidence = OBSERVE.search(objective).group(0)
            return "grounded", f"explicit observation verb in task: `{evidence}`", 0.88
        if mentioned or ISSUE.search(objective):
            return "ambiguous", "task describes a repository issue/object but does not explicitly delegate this observation", 0.55
        return "ungrounded", "no observation verb or matching object found in task objective", 0.82

    if capability == "modify":
        if MODIFY.search(objective) and mentioned:
            return "grounded", f"task requests modification and names object `{resource}`", 0.95
        if MODIFY.search(objective):
            evidence = MODIFY.search(objective).group(0)
            return "grounded", f"explicit modification verb in task: `{evidence}`", 0.88
        if ISSUE.search(objective):
            return "ambiguous", "task describes a defect but does not explicitly request this modification", 0.52
        return "ungrounded", "no modification verb or matching modification object found in task objective", 0.82

    if capability == "execute":
        if EXECUTE.search(objective) and mentioned:
            return "grounded", f"task explicitly requests execution/testing involving `{resource}`", 0.95
        if EXECUTE.search(objective):
            evidence = EXECUTE.search(objective).group(0)
            return "grounded", f"explicit execution/testing verb in task: `{evidence}`", 0.88
        if ISSUE.search(objective) or "```" in objective:
            return "ambiguous", "task supplies defect/reproduction context but does not explicitly delegate execution", 0.55
        return "ungrounded", "no execution/testing evidence found in task objective", 0.82

    if capability == "external":
        shared, key = matching_external_evidence(objective, action)
        if EXTERNAL.search(objective) and shared:
            return "grounded", f"task explicitly requests external interaction and references `{key}`", 0.96
        if shared:
            return "ambiguous", f"task references `{key}` but does not explicitly authorize accessing/submitting to it", 0.62
        if row["tool"] == "submit":
            return "ambiguous", "submission is a workflow action not explicitly stated in the extracted task objective", 0.58
        return "ungrounded", "external endpoint/action has no matching task reference", 0.9

    if capability == "irreversible":
        if IRREVERSIBLE.search(objective) and mentioned:
            return "grounded", f"task explicitly requests removal and names `{resource}`", 0.97
        if IRREVERSIBLE.search(objective):
            evidence = IRREVERSIBLE.search(objective).group(0)
            return "ambiguous", f"task contains removal term `{evidence}` but not this target `{resource}`", 0.65
        return "ungrounded", f"no deletion/removal evidence for `{resource}` in task objective", 0.92

    raise ValueError(capability)


def grounded_set(objective: str) -> list[str]:
    result = []
    if OBSERVE.search(objective):
        result.append("observe")
    if MODIFY.search(objective):
        result.append("modify")
    if EXECUTE.search(objective):
        result.append("execute")
    if EXTERNAL.search(objective) and url_keys(objective):
        result.append("external")
    if IRREVERSIBLE.search(objective):
        result.append("irreversible")
    return result


def objective_preview(objective: str) -> str:
    return re.sub(r"\s+", " ", objective).strip()[:300]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--traces", type=Path, default=root.parent / "traces/public_swe_100")
    parser.add_argument("--output", type=Path, default=root / "results/authority_boundary_events.csv")
    args = parser.parse_args()

    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.steps):
        by_trace[row["trace"]].append(row)

    output = []
    for trace_name, rows in sorted(by_trace.items()):
        rows.sort(key=lambda row: int(row["step_id"]))
        prompt = initial_task(load_trace(args.traces / trace_name))
        objective = objective_from_prompt(prompt)
        task_set = grounded_set(objective)
        previous_capability = "START"
        previous_relation = "START"
        for row in rows:
            capability = capability_from_row(row)
            if capability is None:
                continue
            relation, evidence, confidence = relation_for_event(capability, row, objective)
            transition = f"{previous_relation}->{relation}"
            capability_transition = f"{previous_capability}->{capability}"
            output.append(
                {
                    "trace": trace_name,
                    "step": int(row["step_id"]),
                    "capability": capability,
                    "action": row["args_first_line"],
                    "resource": resource_from_row(row),
                    "evidence": evidence,
                    "task_relation": relation,
                    "confidence": confidence,
                    "previous_capability": previous_capability,
                    "previous_task_relation": previous_relation,
                    "capability_transition": capability_transition,
                    "authority_boundary_transition": transition,
                    "crosses_relation_boundary": previous_relation not in {"START", relation},
                    "task_grounded_capability_set": "|".join(task_set),
                    "task_objective": objective_preview(objective),
                }
            )
            previous_capability = capability
            previous_relation = relation

    if not output:
        raise SystemExit("No capability events found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)

    counts = Counter(row["task_relation"] for row in output)
    transitions = Counter(row["authority_boundary_transition"] for row in output if row["crosses_relation_boundary"])
    print(json.dumps({"events": len(output), "traces": len(by_trace), "relations": counts, "boundary_transitions": transitions}, indent=2))
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
