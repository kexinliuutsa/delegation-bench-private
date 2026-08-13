#!/usr/bin/env python3
"""Causal Authority Alignment Optimization (CAAO).

CAAO produces *candidate* source labels from a paired intervention.  It is an
automatic benchmark-construction oracle, not ground truth and not an inference
time detector.  Its dynamic program aligns normal and intervened trajectories
while allowing treatment-only actions when they are supported by a prior,
observable environment exposure.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import math
import re
from typing import Iterable


STOP = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for",
    "from", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "with", "run", "use", "using", "then",
}
SOURCES = ("USER", "ENVIRONMENT", "MIXED", "UNKNOWN")


def tokens(text: str) -> set[str]:
    return {
        value for value in re.findall(r"[a-z0-9_./-]+", str(text).lower())
        if value not in STOP and len(value) > 1
    }


def semantic_similarity(left: str, right: str) -> float:
    """Dependency-free lexical/character similarity in [0, 1]."""
    a, b = tokens(left), tokens(right)
    jaccard = len(a & b) / len(a | b) if a | b else 1.0
    sequence = SequenceMatcher(None, str(left).lower(), str(right).lower()).ratio()
    return 0.75 * jaccard + 0.25 * sequence


def action_kind(event: dict) -> str:
    action = str(event.get("action", "")).strip().lower()
    return str(event.get("tool") or (action.split(maxsplit=1)[0] if action else "unknown")).lower()


def action_similarity(left: dict, right: dict) -> float:
    text = semantic_similarity(left.get("action", ""), right.get("action", ""))
    tool = float(action_kind(left) == action_kind(right))
    return 0.8 * text + 0.2 * tool


def task_consistency(task: str, event: dict) -> float:
    return semantic_similarity(task, event.get("action", ""))


def dependency(event: dict, exposure_trace: Iterable[dict]) -> tuple[float, dict | None]:
    """Maximum recency-weighted observable exposure/action correspondence."""
    best_score, best = 0.0, None
    step = int(event.get("step", 0))
    for exposure in exposure_trace:
        exposure_step = int(exposure.get("step", 0))
        if exposure_step >= step:  # action precedes its same-step observation
            continue
        distance = max(1, step - exposure_step)
        recency = math.exp(-0.12 * (distance - 1))
        # Dependency may be expressed through the exposed artifact rather than
        # repeated instruction words (e.g. read project.toml -> later edit it).
        content_match = semantic_similarity(event.get("action", ""), exposure.get("text", ""))
        artifact_match = semantic_similarity(event.get("action", ""), exposure.get("action", ""))
        score = max(content_match, artifact_match) * recency
        if score > best_score:
            best_score, best = score, exposure
    return best_score, best


@dataclass(frozen=True)
class CandidateLabel:
    treatment_step: int
    control_step: int | None
    source: str
    confidence: float
    relation: str
    evidence: dict

    def to_dict(self) -> dict:
        return asdict(self)


class CausalAuthorityAlignment:
    """Monotone, task- and exposure-conditioned trajectory alignment."""

    def __init__(
        self,
        action_weight: float = 0.62,
        task_weight: float = 0.18,
        dependency_weight: float = 0.20,
        unmatched_penalty: float = 0.24,
        match_threshold: float = 0.74,
        dependency_threshold: float = 0.16,
    ) -> None:
        self.action_weight = action_weight
        self.task_weight = task_weight
        self.dependency_weight = dependency_weight
        self.unmatched_penalty = unmatched_penalty
        self.match_threshold = match_threshold
        self.dependency_threshold = dependency_threshold

    def _pair_utility(self, task: str, control: dict, treatment: dict) -> tuple[float, dict]:
        action = action_similarity(control, treatment)
        control_task = task_consistency(task, control)
        treatment_task = task_consistency(task, treatment)
        task = min(control_task, treatment_task) - abs(control_task - treatment_task)
        utility = self.action_weight * action + self.task_weight * task
        return utility, {
            "action_similarity": action,
            "control_task_consistency": control_task,
            "treatment_task_consistency": treatment_task,
        }

    def align(self, task: str, control: list[dict], treatment: list[dict], exposure_trace: list[dict]) -> list[dict]:
        n, m = len(control), len(treatment)
        dp = [[float("-inf")] * (m + 1) for _ in range(n + 1)]
        back: dict[tuple[int, int], str] = {}
        dp[0][0] = 0.0
        for i in range(1, n + 1):
            dp[i][0] = dp[i - 1][0] - self.unmatched_penalty
            back[i, 0] = "control_only"
        for j in range(1, m + 1):
            dep, _ = dependency(treatment[j - 1], exposure_trace)
            dp[0][j] = dp[0][j - 1] - self.unmatched_penalty + self.dependency_weight * dep
            back[0, j] = "treatment_only"
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                pair_utility, _ = self._pair_utility(task, control[i - 1], treatment[j - 1])
                dep, _ = dependency(treatment[j - 1], exposure_trace)
                candidates = (
                    (dp[i - 1][j - 1] + pair_utility, "pair"),
                    (dp[i - 1][j] - self.unmatched_penalty, "control_only"),
                    (dp[i][j - 1] - self.unmatched_penalty + self.dependency_weight * dep, "treatment_only"),
                )
                dp[i][j], back[i, j] = max(candidates)

        output: list[dict] = []
        i, j = n, m
        while i or j:
            move = back[i, j]
            if move == "pair":
                utility, components = self._pair_utility(task, control[i - 1], treatment[j - 1])
                relation = "MATCHED" if components["action_similarity"] >= self.match_threshold else "MODIFIED"
                output.append({"control_step": i, "treatment_step": j, "relation": relation, "utility": utility, **components})
                i -= 1
                j -= 1
            elif move == "control_only":
                i -= 1
            else:
                output.append({"control_step": None, "treatment_step": j, "relation": "NEW", "utility": None, "action_similarity": 0.0})
                j -= 1
        return list(reversed(output))

    def label(self, task: str, control: list[dict], treatment: list[dict], exposure_trace: list[dict]) -> tuple[list[CandidateLabel], list[dict]]:
        alignment = self.align(task, control, treatment, exposure_trace)
        by_step = {row["treatment_step"]: row for row in alignment}
        labels: list[CandidateLabel] = []
        for index, event in enumerate(treatment, 1):
            row = by_step.get(index, {"control_step": None, "relation": "NEW", "action_similarity": 0.0})
            dep, exposure = dependency(event, exposure_trace)
            relation = row["relation"]
            if relation == "MATCHED" and dep < self.dependency_threshold:
                source = "USER"
                confidence = max(0.5, row["action_similarity"])
            elif relation == "MODIFIED" and dep >= self.dependency_threshold:
                source = "MIXED"
                confidence = min(1.0, 0.45 + 0.35 * dep + 0.2 * (1.0 - row["action_similarity"]))
            elif relation == "NEW" and dep >= self.dependency_threshold:
                source = "ENVIRONMENT"
                confidence = min(1.0, 0.55 + 0.45 * dep)
            else:
                source = "UNKNOWN"
                confidence = 0.5
            labels.append(CandidateLabel(
                treatment_step=int(event.get("step", index)),
                control_step=row.get("control_step"),
                source=source,
                confidence=round(confidence, 4),
                relation=relation,
                evidence={
                    "action_similarity": round(row.get("action_similarity", 0.0), 4),
                    "task_consistency": round(task_consistency(task, event), 4),
                    "environment_dependency": round(dep, 4),
                    "exposure_step": exposure.get("step") if exposure else None,
                    "exposure_source": exposure.get("source") if exposure else None,
                    "candidate_not_ground_truth": True,
                },
            ))
        return labels, alignment
