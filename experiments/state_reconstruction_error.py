#!/usr/bin/env python3
"""Experiment 9: execution-state reconstruction error analysis.

Observable contradictions are reported as provenance/lifecycle errors. Missing
normative or motivational evidence is reported as authority/intent ambiguity,
not as an error. Categories may overlap.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from context_distance_real import initial_task, load_trace, normalize_resource, parse_capability
from real_swe_security_decision import delete_targets, explicit_task_deletion, read_csv, shell_introductions


INTENT_CUE = re.compile(r"\b(?:clean\s*up|cleanup|remove|delete|temporary|no longer needed|tidy)\b", re.IGNORECASE)


TAXONOMY = {
    "provenance_shell_introduction_missed": {
        "dimension": "provenance_error",
        "definition": "Legacy reconstruction says its normalized target is pre-existing, but raw preceding shell redirection/mkdir/touch/output introduced that target.",
    },
    "provenance_write_creation_conflation": {
        "dimension": "provenance_error",
        "definition": "Legacy reconstruction treats a prior write as creation even though the object was observed before the write.",
    },
    "lifecycle_multi_target_truncation": {
        "dimension": "lifecycle_error",
        "definition": "The shell action targets multiple objects while the normalized delete capability retains only one.",
    },
    "lifecycle_repeated_delete_without_recreation": {
        "dimension": "lifecycle_error",
        "definition": "The same target is deleted again without an intervening observable recreation, so the first action cannot safely imply a completed deleted state.",
    },
    "lifecycle_shell_transition_unmodeled": {
        "dimension": "lifecycle_error",
        "definition": "Creation or introduction occurred in shell syntax but is absent from the normalized capability stream.",
    },
    "authority_not_explicit": {
        "dimension": "authority_ambiguity",
        "definition": "The initial task contains no explicit deletion instruction scoped to the target.",
    },
    "intent_not_explicit": {
        "dimension": "intent_ambiguity",
        "definition": "No matched agent message explicitly states a cleanup/removal intention beyond emitting the rm command.",
    },
    "intent_message_unmatched": {
        "dimension": "intent_ambiguity",
        "definition": "The rm action could not be linked back to an agent message, so stated intent is unobservable.",
    },
}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def assistant_message_for_action(trace: dict[str, Any], action: str) -> str:
    candidates = []
    for message in trace.get("trajectory", []):
        if not isinstance(message, dict) or str(message.get("role", "")).lower() not in {"ai", "assistant"}:
            continue
        text = message.get("text")
        if isinstance(text, str) and action in text:
            candidates.append(text)
    return candidates[-1] if candidates else ""


def intent_explicit(message: str, action: str) -> bool:
    if not message:
        return False
    # Remove the literal command so `rm`/target tokens do not manufacture an
    # intent cue; require explanatory language elsewhere in the message.
    explanatory = message.replace(action, " ")
    explanatory = re.sub(r"```.*?```", " ", explanatory, flags=re.DOTALL)
    return bool(INTENT_CUE.search(explanatory))


def preceding_rows(rows: list[dict[str, str]], step: int) -> list[dict[str, str]]:
    return [row for row in rows if int(row["step_id"]) < step]


def shell_created_targets(prior: list[dict[str, str]]) -> set[str]:
    result = set()
    for row in prior:
        result.update(shell_introductions(row["args_first_line"]))
    return result


def observed_before_write(prior: list[dict[str, str]], target: str) -> bool:
    created = False
    for row in prior:
        parsed = parse_capability(row["capability"])
        if not parsed or normalize_resource(parsed[1]) != target:
            continue
        if parsed[0] == "write" and row["tool"] == "create_file":
            created = True
        elif parsed[0] == "read" and not created:
            return True
    return False


def repeated_without_recreation(
    trace_rows: list[dict[str, str]],
    action_step: int,
    targets: list[str],
) -> bool:
    for target in targets:
        earlier_delete = False
        recreated = False
        for row in trace_rows:
            step = int(row["step_id"])
            if step >= action_step:
                break
            parsed = parse_capability(row["capability"])
            if parsed and normalize_resource(parsed[1]) == target:
                if parsed[0] == "delete":
                    earlier_delete = True
                    recreated = False
                elif earlier_delete and parsed[0] == "write":
                    recreated = True
            if earlier_delete and target in shell_introductions(row["args_first_line"]):
                recreated = True
        if earlier_delete and not recreated:
            return True
    return False


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=root.parent / "results/delete_classification.csv")
    parser.add_argument("--audit", type=Path, default=root / "results/real_swe_security_decision_audit.csv")
    parser.add_argument("--steps", type=Path, default=root.parent / "results/public_swe_100/steps_raw.csv")
    parser.add_argument("--traces", type=Path, default=root.parent / "traces/public_swe_100")
    parser.add_argument("--output", type=Path, default=root / "results/state_reconstruction_errors.csv")
    parser.add_argument("--summary", type=Path, default=root / "results/state_reconstruction_error_summary.csv")
    args = parser.parse_args()

    inventory = {(row["trace"], row["action"]): row for row in read_csv(args.inventory)}
    audit = read_csv(args.audit)
    by_trace: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.steps):
        by_trace[row["trace"]].append(row)
    for rows in by_trace.values():
        rows.sort(key=lambda row: int(row["step_id"]))

    output = []
    category_examples: dict[str, list[str]] = defaultdict(list)
    for audited in audit:
        trace_name = audited["trace"]
        trace_base = trace_name.removesuffix(".json")
        action = audited["action"]
        action_step = int(audited["action_step"])
        targets = delete_targets(action)
        legacy = inventory[(trace_base, action)]
        trace_rows = by_trace[trace_name]
        prior = preceding_rows(trace_rows, action_step)
        trace = load_trace(args.traces / trace_name)
        task = initial_task(trace)
        message = assistant_message_for_action(trace, action)
        shell_targets = shell_created_targets(prior)
        any_shell_introduced = any(target in shell_targets for target in targets)
        preexisting_before_write = any(observed_before_write(prior, target) for target in targets)

        categories = []
        legacy_target = normalize_resource(legacy["target"])
        if legacy["classification"] == "delete_preexisting" and legacy_target in shell_targets:
            categories.append("provenance_shell_introduction_missed")
        if legacy["classification"] == "cleanup" and preexisting_before_write and audited["label"] == "BLOCK":
            categories.append("provenance_write_creation_conflation")
        parsed_action = next((row for row in trace_rows if int(row["step_id"]) == action_step), None)
        parsed = parse_capability(parsed_action["capability"]) if parsed_action else None
        if len(targets) > 1 and parsed and len(targets) > 1 and normalize_resource(parsed[1]) == targets[0]:
            categories.append("lifecycle_multi_target_truncation")
        if repeated_without_recreation(trace_rows, action_step, targets):
            categories.append("lifecycle_repeated_delete_without_recreation")
        if any_shell_introduced:
            categories.append("lifecycle_shell_transition_unmodeled")
        if not explicit_task_deletion(task, targets):
            categories.append("authority_not_explicit")
        if not message:
            categories.append("intent_message_unmatched")
        elif not intent_explicit(message, action):
            categories.append("intent_not_explicit")

        for category in categories:
            if len(category_examples[category]) < 5:
                category_examples[category].append(f"{trace_name}:{action_step}:{action}")
        output.append(
            {
                "trace": trace_name,
                "action_step": action_step,
                "action": action,
                "targets": "|".join(targets),
                "legacy_classification": legacy["classification"],
                "audit_decision": audited["label"],
                "categories": "|".join(categories),
                "provenance_error": any(TAXONOMY[category]["dimension"] == "provenance_error" for category in categories),
                "lifecycle_error": any(TAXONOMY[category]["dimension"] == "lifecycle_error" for category in categories),
                "authority_ambiguity": any(TAXONOMY[category]["dimension"] == "authority_ambiguity" for category in categories),
                "intent_ambiguity": any(TAXONOMY[category]["dimension"] == "intent_ambiguity" for category in categories),
                "agent_message_matched": bool(message),
                "explicit_cleanup_intent": intent_explicit(message, action),
            }
        )

    counts = Counter(category for row in output for category in row["categories"].split("|") if category)
    summary = []
    for category, metadata in TAXONOMY.items():
        count = counts[category]
        summary.append(
            {
                "category": category,
                "dimension": metadata["dimension"],
                "definition": metadata["definition"],
                "count": count,
                "percentage_of_48": round(100 * count / len(output), 2),
                "examples": " || ".join(category_examples[category]),
            }
        )
    for dimension in ("provenance_error", "lifecycle_error", "authority_ambiguity", "intent_ambiguity"):
        count = sum(str(row[dimension]).lower() == "true" for row in output)
        summary.append(
            {
                "category": f"ANY_{dimension.upper()}",
                "dimension": dimension,
                "definition": f"At least one {dimension.replace('_', ' ')} category applies; overlapping categories count once.",
                "count": count,
                "percentage_of_48": round(100 * count / len(output), 2),
                "examples": "",
            }
        )

    write_csv(args.output, output)
    write_csv(args.summary, summary)
    print(json.dumps({row["category"]: {"count": row["count"], "percentage": row["percentage_of_48"]} for row in summary}, indent=2))
    print(f"saved: {args.output}")
    print(f"saved: {args.summary}")


if __name__ == "__main__":
    main()
