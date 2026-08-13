#!/usr/bin/env python3
"""Learned localization model for delegation-risk emergence boundaries."""

from __future__ import annotations
from dataclasses import dataclass
from models.risk_emergence_model import HashedSequenceEncoder,LogisticHead,ObservableSequence

@dataclass(frozen=True)
class BoundaryPrediction:
    boundary_probabilities:tuple[float,...]
    onset_distribution:tuple[float,...]
    no_boundary_probability:float

class DelegationBoundaryModel:
    def __init__(self)->None:self.encoder=HashedSequenceEncoder();self.boundary_head=LogisticHead();self.fitted=False
    def fit(self,sequences:list[ObservableSequence],onset_indices:list[int|None])->None:
        if len(sequences)!=len(onset_indices):raise ValueError('sequence/onset counts differ')
        vectors=[];targets=[]
        for sequence,onset in zip(sequences,onset_indices):
            encoded=self.encoder.encode(sequence);vectors.extend(encoded);targets.extend(int(onset==index) for index in range(1,len(encoded)+1))
        self.boundary_head.fit(vectors,targets,6301);self.fitted=True
    def predict(self,sequence:ObservableSequence)->BoundaryPrediction:
        if not self.fitted:raise RuntimeError('model not fitted')
        probabilities=tuple(self.boundary_head.probability(vector) for vector in self.encoder.encode(sequence));survival=1.0;distribution=[]
        for probability in probabilities:distribution.append(survival*probability);survival*=1-probability
        total=sum(distribution)+survival
        return BoundaryPrediction(probabilities,tuple(value/total for value in distribution),survival/total)
