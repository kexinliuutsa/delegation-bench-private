#!/usr/bin/env python3
"""Factorized Delegation Boundary Reasoner (DBR)."""
from __future__ import annotations
from dataclasses import dataclass
from models.risk_emergence_model import HashedSequenceEncoder,LogisticHead,ObservableSequence

FACTORS=('intent_gap','capability_jump','externality','irreversibility')

@dataclass(frozen=True)
class DBRPrediction:
 factor_probabilities:tuple[dict[str,float],...]
 boundary_probabilities:tuple[float,...]

class DelegationBoundaryReasoner:
 """Learns observable-prefix -> factors; boundary and reason are derived."""
 def __init__(self):self.encoder=HashedSequenceEncoder();self.heads={x:LogisticHead() for x in FACTORS};self.fitted=False
 def fit(self,sequences:list[ObservableSequence],factor_targets:list[list[dict[str,int]]])->None:
  vectors=[];targets={x:[] for x in FACTORS}
  for sequence,labels in zip(sequences,factor_targets):
   encoded=self.encoder.encode(sequence)
   if len(encoded)!=len(labels):raise ValueError('factor target length mismatch')
   vectors.extend(encoded)
   for label in labels:
    for factor in FACTORS:targets[factor].append(int(label.get(factor,0)))
  for seed,(factor,head) in enumerate(self.heads.items(),3601):head.fit(vectors,targets[factor],seed)
  self.fitted=True
 def predict(self,sequence:ObservableSequence)->DBRPrediction:
  if not self.fitted:raise RuntimeError('model not fitted')
  factors=[];boundaries=[]
  for vector in self.encoder.encode(sequence):
   values={name:head.probability(vector) for name,head in self.heads.items()};factors.append(values)
   # No boundary-label head: probability that at least one learned factor holds.
   boundaries.append(1.0-__import__('math').prod(1-value for value in values.values()))
  return DBRPrediction(tuple(factors),tuple(boundaries))

def factors_to_reason(values:dict[str,float],threshold:float=.5)->str|None:
 active={name for name,value in values.items() if value>=threshold}
 # Attribution is a composition over effect factors, not a learned reason ID.
 if values['externality'] or values['irreversibility']:
  return 'external_effect_unrequested' if values['externality']>=values['irreversibility'] else 'irreversible_effect_unrequested'
 if 'capability_jump' in active:return 'authority_scope_exceeded'
 if 'intent_gap' in active:return 'information_scope_exceeded'
 return None
