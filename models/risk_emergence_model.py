#!/usr/bin/env python3
"""Lightweight learned sequence model for risk emergence.

The encoder consumes task text and observable events only. Labels are separate
arguments to ``fit`` and are never stored in inference examples.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from dataclasses import dataclass
from typing import Any


FEATURES = 256


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def feature_index(token: str) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % FEATURES, 1.0 if value & (1 << 63) else -1.0


@dataclass(frozen=True)
class ObservableEvent:
    action: str
    observation: str
    capability: str
    delegation_state: dict[str, str]


@dataclass(frozen=True)
class ObservableSequence:
    task: str
    events: tuple[ObservableEvent, ...]


@dataclass(frozen=True)
class RiskPrediction:
    risk_probabilities: tuple[float, ...]
    onset_distribution: tuple[float, ...]
    no_onset_probability: float


class HashedSequenceEncoder:
    def event_tokens(self, sequence: ObservableSequence, index: int) -> list[str]:
        event = sequence.events[index]
        tokens = [f"task:{word}" for word in words(sequence.task)]
        tokens += [f"action:{word}" for word in words(event.action)]
        tokens += [f"observation:{word}" for word in words(event.observation)]
        tokens.append(f"capability:{event.capability}")
        tokens += [f"state:{key}={value}" for key, value in sorted(event.delegation_state.items())]
        if index:
            previous = sequence.events[index - 1]
            tokens.append(f"capability-edge:{previous.capability}->{event.capability}")
            for key, value in event.delegation_state.items():
                before = previous.delegation_state[key]
                if before != value:
                    tokens.append(f"state-edge:{key}:{before}->{value}")
        task_terms = set(words(sequence.task)); action_terms = set(words(event.action))
        tokens.append(f"task-overlap:{min(len(task_terms & action_terms), 4)}")
        return tokens

    def encode(self, sequence: ObservableSequence) -> list[list[float]]:
        hidden = [0.0] * FEATURES; output = []
        for index in range(len(sequence.events)):
            hidden = [0.72 * value for value in hidden]
            for token in self.event_tokens(sequence, index):
                feature, sign = feature_index(token); hidden[feature] += sign
            norm = math.sqrt(sum(value * value for value in hidden))
            output.append([value / norm for value in hidden] if norm else hidden[:])
        return output


class LogisticHead:
    def __init__(self, feature_count: int = FEATURES) -> None:
        self.weights = [0.0] * feature_count; self.bias = 0.0

    @staticmethod
    def sigmoid(value: float) -> float:
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, value))))

    def probability(self, vector: list[float]) -> float:
        return self.sigmoid(self.bias + sum(weight * value for weight, value in zip(self.weights, vector)))

    def fit(self, vectors: list[list[float]], labels: list[int], seed: int) -> None:
        positives = max(1, sum(labels)); positive_weight = (len(labels) - positives) / positives
        order = list(range(len(labels)))
        for epoch in range(45):
            random.Random(seed + epoch).shuffle(order); rate = 0.09 / math.sqrt(epoch + 1)
            for index in order:
                vector = vectors[index]; probability = self.probability(vector)
                sample_weight = positive_weight if labels[index] else 1.0
                gradient = (probability - labels[index]) * sample_weight
                self.bias -= rate * gradient
                for feature, value in enumerate(vector):
                    if value:
                        self.weights[feature] -= rate * (gradient * value + 1e-4 * self.weights[feature])


class RiskEmergenceModel:
    def __init__(self) -> None:
        self.encoder = HashedSequenceEncoder(); self.risk_head = LogisticHead(); self.onset_head = LogisticHead(); self.fitted = False

    def fit(self, sequences: list[ObservableSequence], risk_targets: list[list[int]], onset_targets: list[list[int]]) -> None:
        if not (len(sequences) == len(risk_targets) == len(onset_targets)):
            raise ValueError("sequence and target counts differ")
        vectors=[];risk=[];onset=[]
        for sequence, risk_values, onset_values in zip(sequences, risk_targets, onset_targets):
            encoded=self.encoder.encode(sequence)
            if not (len(encoded)==len(risk_values)==len(onset_values)):
                raise ValueError("per-sequence target length differs")
            vectors.extend(encoded);risk.extend(risk_values);onset.extend(onset_values)
        self.risk_head.fit(vectors,risk,1701);self.onset_head.fit(vectors,onset,2701);self.fitted=True

    def predict(self, sequence: ObservableSequence) -> RiskPrediction:
        if not self.fitted: raise RuntimeError("model is not fitted")
        vectors=self.encoder.encode(sequence)
        risk=tuple(self.risk_head.probability(vector) for vector in vectors)
        hazards=[self.onset_head.probability(vector) for vector in vectors]
        survival=1.0;distribution=[]
        for hazard in hazards:
            distribution.append(survival*hazard);survival*=1-hazard
        total=sum(distribution)+survival
        return RiskPrediction(risk,tuple(value/total for value in distribution),survival/total)
