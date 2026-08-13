#!/usr/bin/env python3
"""Safe-only intent-conditioned delegation prior.

This model fits capability necessity and state expectations using only safe
observable sequences. It is a one-class model: no risk annotations are accepted
by ``fit`` or ``predict``.
"""

from __future__ import annotations

import bisect
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from models.delegation_state import RANKS, VALUE_ORDERS
from models.risk_emergence_model import ObservableSequence, RiskPrediction


CAPABILITIES=("observe","modify","execute","external","irreversible")
DIMENSIONS=tuple(VALUE_ORDERS)


def intent_flags(task:str)->frozenset[str]:
    value=task.lower();flags=set()
    patterns={
        'local':r'\b(repository|patch|parser|document|editor|file)\b',
        'web':r'\b(product|public|search|option)\b',
        'modify':r'\b(repair|format|edit|save|patch)\b',
        'execute':r'\b(test|tested|repair|parser)\b',
        'report':r'\b(report|submit)\b',
        'no_purchase':r'\bwithout purchasing\b',
    }
    for name,pattern in patterns.items():
        if re.search(pattern,value):flags.add(name)
    return frozenset(flags or {'generic'})


@dataclass(frozen=True)
class DelegationPrior:
    expected_capability_probabilities:dict[str,float]
    expected_capability_set:frozenset[str]
    expected_state_ranks:dict[str,float]


@dataclass(frozen=True)
class PriorDeviation:
    actual_capability:str
    expected_capability_set:frozenset[str]
    deviation_vector:tuple[float,...]
    raw_deviation_score:float


class IntentConditionedDelegationPriorModel:
    def __init__(self)->None:
        self.global_capability:dict[int,Counter[str]]=defaultdict(Counter);self.flag_capability:dict[tuple[str,int],Counter[str]]=defaultdict(Counter)
        self.global_presence:Counter[str]=Counter();self.flag_presence:dict[str,Counter[str]]=defaultdict(Counter);self.sequence_count=0;self.flag_sequence_count:Counter[str]=Counter()
        self.global_state:dict[tuple[int,str],list[int]]=defaultdict(list);self.flag_state:dict[tuple[str,int,str],list[int]]=defaultdict(list)
        self.safe_score_distribution:list[float]=[];self.fitted=False

    @staticmethod
    def position(index:int,length:int)->int:return round(index*5/max(1,length-1))

    def fit(self,safe_sequences:list[ObservableSequence])->None:
        if not safe_sequences:raise ValueError('safe sequences required')
        for sequence in safe_sequences:
            flags=intent_flags(sequence.task)
            present={event.capability for event in sequence.events};self.sequence_count+=1;self.global_presence.update(present)
            for flag in flags:self.flag_sequence_count[flag]+=1;self.flag_presence[flag].update(present)
            for index,event in enumerate(sequence.events):
                position=self.position(index,len(sequence.events));self.global_capability[position][event.capability]+=1
                for flag in flags:self.flag_capability[(flag,position)][event.capability]+=1
                for dimension in DIMENSIONS:
                    rank=RANKS[dimension][event.delegation_state[dimension]];self.global_state[(position,dimension)].append(rank)
                    for flag in flags:self.flag_state[(flag,position,dimension)].append(rank)
        # Calibrate only against scores of known-safe prefixes.
        scores=[]
        for sequence in safe_sequences:scores.extend(item.raw_deviation_score for item in self.deviations(sequence))
        self.safe_score_distribution=sorted(scores);self.fitted=True

    def prior(self,task:str,index:int,length:int)->DelegationPrior:
        position=self.position(index,length);flags=intent_flags(task);global_counts=self.global_capability[position];combined=Counter()
        for capability in CAPABILITIES:
            combined[capability]+=global_counts[capability]
        for flag in flags:combined.update(self.flag_capability.get((flag,position),{}))
        # Necessity is trajectory-level presence, not a rigid positional script.
        probabilities={}
        for capability in CAPABILITIES:
            numerator=self.global_presence[capability];denominator=self.sequence_count
            for flag in flags:numerator+=self.flag_presence[flag][capability];denominator+=self.flag_sequence_count[flag]
            probabilities[capability]=(numerator+0.5)/(denominator+1.0)
        expected=frozenset(capability for capability,probability in probabilities.items() if probability>=0.5)
        state_ranks={}
        for dimension in DIMENSIONS:
            values=list(self.global_state[(position,dimension)])
            for flag in flags:values.extend(self.flag_state.get((flag,position,dimension),[]))
            state_ranks[dimension]=sum(values)/len(values) if values else 0.0
        return DelegationPrior(probabilities,expected,state_ranks)

    def deviations(self,sequence:ObservableSequence)->list[PriorDeviation]:
        output=[];previous=None
        for index,event in enumerate(sequence.events):
            prior=self.prior(sequence.task,index,len(sequence.events));necessity=prior.expected_capability_probabilities.get(event.capability,0.0);vector=[1-necessity,float(event.capability not in prior.expected_capability_set),float(previous is not None and previous!=event.capability)]
            excess=[]
            for dimension in DIMENSIONS:
                actual=RANKS[dimension][event.delegation_state[dimension]];scale=max(1,len(VALUE_ORDERS[dimension])-1);value=max(0.0,actual-prior.expected_state_ranks[dimension])/scale;vector.append(value);excess.append(value)
            score=0.5*vector[0]+0.2*vector[1]+0.3*max(excess)
            output.append(PriorDeviation(event.capability,prior.expected_capability_set,tuple(vector),score));previous=event.capability
        return output

    def probability(self,score:float)->float:
        if not self.safe_score_distribution:raise RuntimeError('model not fitted')
        # Safe-only upper-tail calibration. Ordinary safe variation maps to zero;
        # only the most anomalous 5% of the fitted safe distribution maps upward.
        cdf=(bisect.bisect_left(self.safe_score_distribution,score)+1)/(len(self.safe_score_distribution)+2)
        return max(0.0,min(1.0,(cdf-0.95)/0.05))

    def predict(self,sequence:ObservableSequence)->RiskPrediction:
        if not self.fitted:raise RuntimeError('model not fitted')
        probabilities=tuple(self.probability(item.raw_deviation_score) for item in self.deviations(sequence));survival=1.0;distribution=[];previous=0.0
        for probability in probabilities:
            hazard=max(0.0,probability-previous);distribution.append(survival*hazard);survival*=1-hazard;previous=max(previous,probability)
        total=sum(distribution)+survival
        return RiskPrediction(probabilities,tuple(value/total for value in distribution),survival/total)

    def expected_delegation_prior(self,sequence:ObservableSequence)->tuple[DelegationPrior,...]:
        return tuple(self.prior(sequence.task,index,len(sequence.events)) for index in range(len(sequence.events)))
