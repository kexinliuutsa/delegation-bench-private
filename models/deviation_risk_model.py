#!/usr/bin/env python3
"""Intent-conditioned delegation deviation model.

Expected envelopes are fitted exclusively from task text and safe training
sequences. Risk/onset targets supervise separate heads and are not inference
features.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from models.delegation_state import RANKS, VALUE_ORDERS
from models.risk_emergence_model import LogisticHead, ObservableSequence, RiskPrediction


DIMENSIONS=tuple(VALUE_ORDERS)


def task_terms(task:str)->frozenset[str]:
    stop={'a','an','and','for','in','my','of','the','to','without','it'}
    return frozenset(token for token in re.findall(r'[a-z]+',task.lower()) if token not in stop)


def similarity(left:frozenset[str],right:frozenset[str])->float:
    return len(left&right)/len(left|right) if left|right else 1.0


@dataclass(frozen=True)
class EnvelopeProfile:
    intent_terms:frozenset[str]
    capabilities:tuple[str,...]
    states:tuple[dict[str,str],...]


@dataclass(frozen=True)
class DeviationSnapshot:
    expected_capability_set:frozenset[str]
    actual_capability_set:frozenset[str]
    deviation_vector:tuple[float,...]


class IntentEnvelope:
    def __init__(self)->None:self.profiles:list[EnvelopeProfile]=[]
    def fit(self,safe_sequences:list[ObservableSequence])->None:
        self.profiles=[EnvelopeProfile(task_terms(sequence.task),tuple(event.capability for event in sequence.events),tuple(dict(event.delegation_state) for event in sequence.events)) for sequence in safe_sequences]
        if not self.profiles:raise ValueError('at least one safe sequence is required')
    def nearest(self,task:str)->list[EnvelopeProfile]:
        query=task_terms(task);scores=[similarity(query,profile.intent_terms) for profile in self.profiles];best=max(scores)
        selected=[profile for profile,score in zip(self.profiles,scores) if score==best]
        return selected[:20]
    def snapshots(self,sequence:ObservableSequence)->list[DeviationSnapshot]:
        profiles=self.nearest(sequence.task);actual_caps:set[str]=set();output=[]
        previous_capability=None
        for index,event in enumerate(sequence.events):
            actual_caps.add(event.capability);position=min(index,min(len(profile.capabilities) for profile in profiles)-1)
            expected_current={profile.capabilities[position] for profile in profiles}
            expected_prefix={capability for profile in profiles for capability in profile.capabilities[:position+1]}
            unexpected_current=float(event.capability not in expected_current)
            unexpected_set=actual_caps-expected_prefix;missing_set=expected_prefix-actual_caps
            vector=[unexpected_current,float(len(unexpected_set))/5,float(len(missing_set))/5,float(event.capability!=previous_capability if previous_capability else 0),index/max(1,len(sequence.events)-1)]
            for dimension in DIMENSIONS:
                actual_rank=RANKS[dimension][event.delegation_state[dimension]]
                expected_ranks=[RANKS[dimension][profile.states[position][dimension]] for profile in profiles]
                scale=max(1,len(VALUE_ORDERS[dimension])-1)
                vector.append(max(0,actual_rank-max(expected_ranks))/scale)
                vector.append(max(0,min(expected_ranks)-actual_rank)/scale)
            vector.extend([
                float(event.delegation_state['information_scope']=='credential'),
                float(event.delegation_state['external_effect'] in {'communication','financial','irreversible'} and all(profile.states[position]['external_effect']=='none' for profile in profiles)),
                float(event.delegation_state['persistence_level']=='persistent' and all(profile.states[position]['persistence_level']!='persistent' for profile in profiles)),
            ])
            output.append(DeviationSnapshot(frozenset(expected_prefix),frozenset(actual_caps),tuple(vector)));previous_capability=event.capability
        return output


class DeviationRiskModel:
    def __init__(self)->None:self.envelope=IntentEnvelope();self.risk_head:LogisticHead|None=None;self.onset_head:LogisticHead|None=None
    def fit(self,safe_sequences:list[ObservableSequence],sequences:list[ObservableSequence],risk_targets:list[list[int]],onset_targets:list[list[int]])->None:
        self.envelope.fit(safe_sequences);vectors=[];risk=[];onset=[]
        for sequence,risk_values,onset_values in zip(sequences,risk_targets,onset_targets):
            snapshots=self.envelope.snapshots(sequence)
            if not(len(snapshots)==len(risk_values)==len(onset_values)):raise ValueError('target length mismatch')
            vectors.extend([list(snapshot.deviation_vector) for snapshot in snapshots]);risk.extend(risk_values);onset.extend(onset_values)
        size=len(vectors[0]);self.risk_head=LogisticHead(size);self.onset_head=LogisticHead(size);self.risk_head.fit(vectors,risk,3801);self.onset_head.fit(vectors,onset,4801)
    def predict(self,sequence:ObservableSequence)->RiskPrediction:
        if self.risk_head is None or self.onset_head is None:raise RuntimeError('model not fitted')
        vectors=[list(snapshot.deviation_vector) for snapshot in self.envelope.snapshots(sequence)]
        risk=tuple(self.risk_head.probability(vector) for vector in vectors);hazards=[self.onset_head.probability(vector) for vector in vectors];survival=1.0;distribution=[]
        for hazard in hazards:distribution.append(survival*hazard);survival*=1-hazard
        total=sum(distribution)+survival
        return RiskPrediction(risk,tuple(value/total for value in distribution),survival/total)

    def explain_prefix(self,sequence:ObservableSequence)->tuple[DeviationSnapshot,...]:
        return tuple(self.envelope.snapshots(sequence))
