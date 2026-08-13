#!/usr/bin/env python3
"""Experiment 15: learned algorithms for latent delegation-state inference.

Training oracle states are permitted for fitting. At test time, algorithms see
only task text and observable trajectory fields. ``LLM-style simulator`` is a
deterministic TF-IDF nearest-neighbor proxy over full-history text; it is not an
evaluation of an actual language model.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.delegation_state import DEFAULT_STATE, DelegationState, state_transition


StateKey = tuple[str, str, str, str, str]


def state_key(state: DelegationState) -> StateKey:
    value = state.to_dict()
    return tuple(value[key] for key in value)  # type: ignore[return-value]


def key_state(key: StateKey) -> DelegationState:
    return DelegationState(*key)


@dataclass(frozen=True)
class PredictionView:
    sample_id: str
    task: str
    actions: tuple[str, ...]
    observations: tuple[str, ...]
    horizon: int


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def observable_capability(action: str) -> str:
    value = action.lower()
    if re.search(r"\b(?:delete|remove|unlink)\b", value):
        return "delete"
    if re.search(r"\b(?:buy|book|purchase|pay|checkout)\b", value):
        return "transaction"
    if re.search(r"\b(?:send|message|email|submit|publish|dispatch)\b", value):
        return "submit"
    if re.search(r"\b(?:execute|run|validate|test)\b", value):
        return "execute"
    if re.search(r"\b(?:edit|update|change|create|draft|compose|enter|select|add)\b", value):
        return "modify"
    return "observe"


class Vectorizer:
    def __init__(self, documents: Iterable[str]) -> None:
        docs = [set(tokenize(document)) for document in documents]
        frequencies = Counter(token for doc in docs for token in doc)
        count = len(docs)
        self.idf = {token: math.log((count + 1) / (frequency + 1)) + 1 for token, frequency in frequencies.items()}

    def transform(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        vector = {token: count * self.idf.get(token, 0.0) for token, count in counts.items() if token in self.idf}
        norm = math.sqrt(sum(value * value for value in vector.values()))
        return {token: value / norm for token, value in vector.items()} if norm else {}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(token, 0.0) for token, value in left.items())


def select_label(scores: dict[StateKey, float], priors: Counter[StateKey]) -> StateKey:
    return max(scores, key=lambda key: (scores[key], priors[key], key))


def deep_size(value: Any, seen: set[int] | None = None) -> int:
    """Deterministic recursive Python-object footprint estimate."""
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    total = sys.getsizeof(value)
    if isinstance(value, dict):
        total += sum(deep_size(key, seen) + deep_size(item, seen) for key, item in value.items())
    elif isinstance(value, (list, tuple, set, frozenset, Counter)):
        total += sum(deep_size(item, seen) for item in value)
    elif hasattr(value, "__dict__"):
        total += deep_size(vars(value), seen)
    return total


class ActionMapper:
    name = "M0_action_mapper"

    def __init__(self, examples: list[tuple[str, StateKey]]) -> None:
        grouped: dict[str, Counter[StateKey]] = defaultdict(Counter)
        self.priors: Counter[StateKey] = Counter()
        for action, label in examples:
            grouped[action.lower()][label] += 1
            self.priors[label] += 1
        self.mapping = {action: counts.most_common(1)[0][0] for action, counts in grouped.items()}
        self.default = self.priors.most_common(1)[0][0]

    def predict(self, view: PredictionView) -> list[DelegationState]:
        return [DEFAULT_STATE, *[key_state(self.mapping.get(action.lower(), self.default)) for action in view.actions]]

    def runtime_bytes(self, view: PredictionView, step: int) -> int:
        return deep_size(view.actions[step - 1])


class CapabilityMapper:
    name = "M1_capability_mapper"

    def __init__(self, examples: list[tuple[str, StateKey]]) -> None:
        documents = [document for document, _ in examples]
        self.vectorizer = Vectorizer(documents)
        self.priors: Counter[StateKey] = Counter(label for _, label in examples)
        sums: dict[StateKey, Counter[str]] = defaultdict(Counter)
        counts: Counter[StateKey] = Counter()
        for document, label in examples:
            sums[label].update(self.vectorizer.transform(document))
            counts[label] += 1
        self.centroids = {
            label: {token: value / counts[label] for token, value in vector.items()}
            for label, vector in sums.items()
        }

    @staticmethod
    def document(task: str, action: str) -> str:
        return f"{task} capability_{observable_capability(action)}"

    def infer(self, task: str, action: str) -> DelegationState:
        vector = self.vectorizer.transform(self.document(task, action))
        scores = {label: cosine(vector, centroid) for label, centroid in self.centroids.items()}
        return key_state(select_label(scores, self.priors))

    def predict(self, view: PredictionView) -> list[DelegationState]:
        return [DEFAULT_STATE, *[self.infer(view.task, action) for action in view.actions]]

    def runtime_bytes(self, view: PredictionView, step: int) -> int:
        return deep_size((view.task, view.actions[step - 1], observable_capability(view.actions[step - 1])))


class FullHistoryRetrieval:
    name = "M2_llm_style_history_simulator"

    def __init__(self, examples: list[tuple[str, StateKey]]) -> None:
        documents = [document for document, _ in examples]
        self.vectorizer = Vectorizer(documents)
        self.examples = [(self.vectorizer.transform(document), label) for document, label in examples]
        self.priors: Counter[StateKey] = Counter(label for _, label in examples)

    @staticmethod
    def document(view: PredictionView, step: int) -> str:
        history = " ".join(
            f"action {action} observation {observation}"
            for action, observation in zip(view.actions[:step], view.observations[:step])
        )
        return f"task {view.task} history {history}"

    def infer(self, document: str) -> DelegationState:
        vector = self.vectorizer.transform(document)
        best_vector, best_label = max(
            self.examples,
            key=lambda item: (cosine(vector, item[0]), self.priors[item[1]], item[1]),
        )
        del best_vector
        return key_state(best_label)

    def predict(self, view: PredictionView) -> list[DelegationState]:
        return [DEFAULT_STATE, *[self.infer(self.document(view, step)) for step in range(1, len(view.actions) + 1)]]

    def runtime_bytes(self, view: PredictionView, step: int) -> int:
        return deep_size((view.task, view.actions[:step], view.observations[:step]))


class DelegationEvolutionGraph:
    name = "M3_delegation_evolution_graph"

    def __init__(self, examples: list[tuple[StateKey, str, StateKey]]) -> None:
        documents = [document for _, document, _ in examples]
        self.vectorizer = Vectorizer(documents)
        self.edges: dict[StateKey, list[tuple[dict[str, float], StateKey]]] = defaultdict(list)
        self.all_edges: list[tuple[dict[str, float], StateKey]] = []
        self.priors: Counter[StateKey] = Counter()
        for previous, document, target in examples:
            item = (self.vectorizer.transform(document), target)
            self.edges[previous].append(item)
            self.all_edges.append(item)
            self.priors[target] += 1

    @staticmethod
    def document(task: str, action: str, observation: str) -> str:
        return f"task {task} capability_{observable_capability(action)} action {action} observation {observation}"

    def update(self, previous: DelegationState, action: str, observation: str, task: str) -> tuple[DelegationState, dict[str, Any]]:
        vector = self.vectorizer.transform(self.document(task, action, observation))
        candidates = self.edges.get(state_key(previous), self.all_edges)
        _, target = max(candidates, key=lambda item: (cosine(vector, item[0]), self.priors[item[1]], item[1]))
        current = key_state(target)
        return current, state_transition(previous, current)

    def predict(self, view: PredictionView) -> list[DelegationState]:
        states = [DEFAULT_STATE]
        current = DEFAULT_STATE
        for action, observation in zip(view.actions, view.observations):
            current, _ = self.update(current, action, observation, view.task)
            states.append(current)
        return states

    def runtime_bytes(self, view: PredictionView, step: int) -> int:
        return deep_size((view.task, view.actions[step - 1], view.observations[step - 1], DEFAULT_STATE))


def category_horizon(sample_id: str, trajectory_length: int) -> tuple[str, int]:
    match = re.match(r"dbv0_(.+)_(?:short|medium|long)_\d+$", sample_id)
    if not match:
        raise ValueError(f"unexpected sample id: {sample_id}")
    return match.group(1), trajectory_length


def split_samples(samples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        groups[category_horizon(sample["id"], len(sample["trajectory"]))].append(sample)
    training, testing = [], []
    for key, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda sample: sample["id"])
        test_count = 2
        training.extend(ordered[:-test_count])
        testing.extend(ordered[-test_count:])
    return training, testing


def sanitized_view(sample: dict[str, Any]) -> PredictionView:
    return PredictionView(
        sample_id=sample["id"], task=sample["task"],
        actions=tuple(event["action"] for event in sample["trajectory"]),
        observations=tuple(event["observation"] for event in sample["trajectory"]),
        horizon=len(sample["trajectory"]),
    )


def training_examples(training: list[dict[str, Any]]) -> tuple[list[tuple[str, StateKey]], list[tuple[str, StateKey]], list[tuple[str, StateKey]], list[tuple[StateKey, str, StateKey]]]:
    action_examples=[]; capability_examples=[]; history_examples=[]; graph_examples=[]
    for sample in training:
        view = sanitized_view(sample)
        oracle = [DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step, (action, observation) in enumerate(zip(view.actions, view.observations), start=1):
            label=state_key(oracle[step])
            action_examples.append((action,label))
            capability_examples.append((CapabilityMapper.document(view.task,action),label))
            history_examples.append((FullHistoryRetrieval.document(view,step),label))
            graph_examples.append((state_key(oracle[step-1]),DelegationEvolutionGraph.document(view.task,action,observation),label))
    return action_examples,capability_examples,history_examples,graph_examples


def binary_f1(truth: list[bool], predicted: list[bool]) -> float:
    tp=sum(a and b for a,b in zip(truth,predicted)); fp=sum(not a and b for a,b in zip(truth,predicted)); fn=sum(a and not b for a,b in zip(truth,predicted))
    return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0


def evaluate(testing: list[dict[str, Any]], algorithms: list[Any]) -> list[dict[str, Any]]:
    records=[]
    for algorithm in algorithms:
        buckets: dict[str, dict[str, list[Any]]] = defaultdict(lambda: {"exact":[],"truth_transition":[],"pred_transition":[],"runtime":[]})
        for sample in testing:
            view=sanitized_view(sample)
            predicted=algorithm.predict(view)
            # Test oracles are evaluation-only and accessed after prediction.
            oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
            for step in range(1,len(oracle)):
                values=(predicted[step]==oracle[step],bool(state_transition(oracle[step-1],oracle[step])["changed"]),bool(state_transition(predicted[step-1],predicted[step])["changed"]),algorithm.runtime_bytes(view,step))
                for bucket in ("overall",str(view.horizon)):
                    buckets[bucket]["exact"].append(values[0]); buckets[bucket]["truth_transition"].append(values[1]); buckets[bucket]["pred_transition"].append(values[2]); buckets[bucket]["runtime"].append(values[3])
        model_bytes=deep_size(algorithm)
        for bucket in ("overall","5","10","20"):
            data=buckets[bucket]
            records.append({
                "algorithm":algorithm.name,"horizon":bucket,
                "state_recovery_accuracy":round(mean(data["exact"]),4),
                "transition_detection_f1":round(binary_f1(data["truth_transition"],data["pred_transition"]),4),
                "model_memory_bytes":model_bytes,
                "mean_runtime_context_bytes":round(mean(data["runtime"]),1),
                "evaluated_states":len(data["exact"]),
            })
    return records


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width,height=1040,570; left,right,top,bottom=75,35,55,75
    panel_w=(width-left-right-50)/2; plot_h=height-top-bottom
    colors={"M0_action_mapper":"#64748b","M1_capability_mapper":"#f59e0b","M2_llm_style_history_simulator":"#8b5cf6","M3_delegation_evolution_graph":"#2563eb"}
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="520" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation inference by trajectory horizon</text>']
    horizons=(5,10,20)
    for panel,(field,title) in enumerate((("state_recovery_accuracy","State recovery accuracy"),("transition_detection_f1","Transition detection F1"))):
        x0=left+panel*(panel_w+50)
        for tick in range(0,11,2):
            value=tick/10;y=top+plot_h*(1-value)
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_w}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            parts.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>')
        parts.append(f'<text x="{x0+panel_w/2:.1f}" y="{top-12}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for algorithm,color in colors.items():
            points=[]
            for index,horizon in enumerate(horizons):
                row=next(r for r in rows if r["algorithm"]==algorithm and r["horizon"]==str(horizon))
                x=x0+panel_w*index/(len(horizons)-1);y=top+plot_h*(1-float(row[field]));points.append((x,y))
            coords=" ".join(f"{x:.1f},{y:.1f}" for x,y in points)
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            for x,y in points: parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        for index,horizon in enumerate(horizons):
            x=x0+panel_w*index/(len(horizons)-1);parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index,(algorithm,color) in enumerate(colors.items()):
        x=left+index*235;parts.append(f'<rect x="{x}" y="{height-28}" width="12" height="12" fill="{color}"/>');parts.append(f'<text x="{x+17}" y="{height-18}" font-family="sans-serif" font-size="10">{algorithm}</text>')
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text("\n".join(parts),encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--benchmark",type=Path,default=ROOT/"benchmarks/delegationbench/delegationbench_v0.json")
    parser.add_argument("--output",type=Path,default=ROOT/"results/delegation_inference_results.csv")
    parser.add_argument("--plot",type=Path,default=ROOT/"results/delegation_inference_horizon.svg")
    args=parser.parse_args()
    samples=json.loads(args.benchmark.read_text(encoding="utf-8"));training,testing=split_samples(samples)
    examples=training_examples(training)
    algorithms=[ActionMapper(examples[0]),CapabilityMapper(examples[1]),FullHistoryRetrieval(examples[2]),DelegationEvolutionGraph(examples[3])]
    rows=evaluate(testing,algorithms);write_csv(args.output,rows);write_svg(args.plot,rows)
    overall=[row for row in rows if row["horizon"]=="overall"]
    print(json.dumps({
        "training_trajectories":len(training),"testing_trajectories":len(testing),
        "test_horizon_distribution":Counter(len(sample["trajectory"]) for sample in testing),
        "overall_results":overall,
        "oracle_isolation":"PredictionView contains task/actions/observations only; test labels are evaluation-only.",
        "llm_simulator_note":"TF-IDF full-history retrieval proxy; no actual LLM was evaluated.",
    },indent=2))


if __name__=="__main__":
    main()
