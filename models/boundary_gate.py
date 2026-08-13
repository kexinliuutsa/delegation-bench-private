#!/usr/bin/env python3
"""Calibrated trajectory-level gate for delegation-boundary presence."""
from __future__ import annotations
import re
from dataclasses import dataclass
from models.delegation_state import RANKS
from models.risk_emergence_model import LogisticHead,ObservableSequence
@dataclass(frozen=True)
class GatePrediction:
 boundary_probability:float
 boundary_present:bool
class BoundaryGate:
 def __init__(self):self.head:LogisticHead|None=None;self.decision_threshold=.5
 def features(self,sequence:ObservableSequence)->list[float]:
  task=sequence.task.lower();n=len(sequence.events);values=[];previous=None
  credential=irreversible=early_external=persistent_execute=early_account_modify=0.;high_impact_positions=[];cap_counts={name:0 for name in ('observe','modify','execute','external','irreversible')};state_change_count=0
  for index,event in enumerate(sequence.events,1):
   state=event.delegation_state;cap_counts[event.capability]=cap_counts.get(event.capability,0)+1
   credential=max(credential,float(state['information_scope']=='credential'));irreversible=max(irreversible,float(state['external_effect']=='irreversible'))
   early_external=max(early_external,float(index<n and state['external_effect'] in {'communication','financial'}));persistent_execute=max(persistent_execute,float(event.capability=='execute' and state['persistence_level']=='persistent'))
   early_account_modify=max(early_account_modify,float(index<n and state['resource_scope']=='account' and state['operation_scope']=='modify'))
   if event.capability in {'execute','external','irreversible'}:high_impact_positions.append(index/n)
   if previous is not None:state_change_count+=sum(previous[key]!=state[key] for key in state)
   previous=state
  requested_external=float(bool(re.search(r'\b(submit|report|send|purchase|book)\b',task)));requested_persistent=float(bool(re.search(r'\b(save|submit|patch|format)\b',task)))
  values.extend([credential,irreversible,early_external,persistent_execute,early_account_modify,requested_external,requested_persistent,state_change_count/(n*5),min(high_impact_positions or [1.0]),len(high_impact_positions)/n])
  values.extend(cap_counts[name]/n for name in ('observe','modify','execute','external','irreversible'))
  # Interactions express deviation from intent without surface action tokens.
  values.extend([early_external*(1-requested_external),irreversible*(1-requested_persistent),persistent_execute,credential])
  return values
 def fit(self,sequences:list[ObservableSequence],presence_targets:list[int])->None:
  if len(sequences)!=len(presence_targets):raise ValueError('sequence/target counts differ')
  # Deterministic internal fit/calibration split; all data remain training-domain.
  fit_indices=[i for i in range(len(sequences)) if i%5!=0];calibration=[i for i in range(len(sequences)) if i%5==0];vectors=[self.features(x) for x in sequences];self.head=LogisticHead(len(vectors[0]));self.head.fit([vectors[i] for i in fit_indices],[presence_targets[i] for i in fit_indices],9301)
  safe_calibration=[self.head.probability(vectors[i]) for i in calibration if not presence_targets[i]]
  candidates=sorted({self.head.probability(vectors[i]) for i in calibration}|({max(safe_calibration)+1e-6} if safe_calibration else set()))
  best=(float('-inf'),.5)
  for threshold in candidates:
   safe=[i for i in calibration if not presence_targets[i]];false_rate=sum(self.head.probability(vectors[i])>=threshold for i in safe)/max(1,len(safe))
   tp=sum(presence_targets[i] and self.head.probability(vectors[i])>=threshold for i in calibration);fp=sum(not presence_targets[i] and self.head.probability(vectors[i])>=threshold for i in calibration);fn=sum(presence_targets[i] and self.head.probability(vectors[i])<threshold for i in calibration);f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0
   objective=f1 if false_rate<=.1 else f1-2*false_rate
   if objective>best[0]:best=(objective,threshold)
  self.decision_threshold=best[1]
 def predict(self,sequence:ObservableSequence)->GatePrediction:
  if self.head is None:raise RuntimeError('gate not fitted')
  probability=self.head.probability(self.features(sequence));return GatePrediction(probability,probability>=self.decision_threshold)
