#!/usr/bin/env python3
"""Joint learned onset-localization and authority-attribution model."""
from __future__ import annotations
from dataclasses import dataclass
from models.delegation_boundary_model import DelegationBoundaryModel
from models.risk_emergence_model import HashedSequenceEncoder,LogisticHead,ObservableSequence
ATTRIBUTIONS=('authority_scope_exceeded','information_scope_exceeded','external_effect_unrequested','irreversible_effect_unrequested')
@dataclass(frozen=True)
class BoundaryAttributionPrediction:
 boundary_probabilities:tuple[float,...]
 onset_distribution:tuple[float,...]
 no_boundary_probability:float
 attribution_probabilities:tuple[dict[str,float],...]
class DelegationBoundaryAttributionModel:
 def __init__(self):self.boundary=DelegationBoundaryModel();self.encoder=HashedSequenceEncoder();self.heads={name:LogisticHead() for name in ATTRIBUTIONS};self.fitted=False
 def fit(self,sequences:list[ObservableSequence],boundary_steps:list[int|None],attributions:list[str|None])->None:
  self.boundary.fit(sequences,boundary_steps);vectors=[];targets={name:[] for name in ATTRIBUTIONS}
  for sequence,boundary,attribution in zip(sequences,boundary_steps,attributions):
   encoded=self.encoder.encode(sequence);vectors.extend(encoded)
   for index in range(1,len(encoded)+1):
    for name in ATTRIBUTIONS:targets[name].append(int(index==boundary and attribution==name))
  for offset,name in enumerate(ATTRIBUTIONS):self.heads[name].fit(vectors,targets[name],7301+offset*101)
  self.fitted=True
 def predict(self,sequence:ObservableSequence)->BoundaryAttributionPrediction:
  if not self.fitted:raise RuntimeError('model not fitted')
  boundary=self.boundary.predict(sequence);vectors=self.encoder.encode(sequence);attributions=tuple({name:self.heads[name].probability(vector) for name in ATTRIBUTIONS} for vector in vectors)
  return BoundaryAttributionPrediction(boundary.boundary_probabilities,boundary.onset_distribution,boundary.no_boundary_probability,attributions)
