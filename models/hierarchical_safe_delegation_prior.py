#!/usr/bin/env python3
"""Hierarchical intent-conditioned safe delegation prior."""
from __future__ import annotations
import hashlib,math,re
from collections import Counter
from statistics import mean,pstdev
from models.delegation_transition_encoder import transition_signature
from models.intent_conditioned_transition_alignment import IntentConditionedTransitionAlignment
from models.risk_emergence_model import ObservableSequence

TASK_DIM=128
def task_vector(text):
 values=[0.0]*TASK_DIM
 for word in re.findall(r'[a-z]+',text.lower()):
  digest=hashlib.blake2b(word.encode(),digest_size=8).digest();number=int.from_bytes(digest,'big');values[number%TASK_DIM]+=1 if number>>63 else -1
 norm=math.sqrt(sum(x*x for x in values));return tuple(x/norm for x in values) if norm else tuple(values)
def cosine(a,b):return sum(x*y for x,y in zip(a,b))

class HierarchicalSafeDelegationPrior(IntentConditionedTransitionAlignment):
 def __init__(self,regimes=4):super().__init__();self.regimes=regimes;self.centers=[];self.regime_counts=[];self.calibration=[]
 def cluster(self,vectors):
  centers=[list(vectors[i*len(vectors)//self.regimes]) for i in range(self.regimes)]
  for _ in range(20):
   assign=[max(range(self.regimes),key=lambda c:cosine(v,centers[c])) for v in vectors]
   for c in range(self.regimes):
    members=[vectors[i] for i,a in enumerate(assign) if a==c]
    if members:
     center=[mean(x) for x in zip(*members)];norm=math.sqrt(sum(x*x for x in center));centers[c]=[x/norm for x in center]
  return [tuple(x) for x in centers],assign
 def regime(self,task):
  vector=task_vector(task);return max(range(len(self.centers)),key=lambda c:cosine(vector,self.centers[c]))
 def fit(self,safe_sequences:list[ObservableSequence])->None:
  # Parent learns DTE alignment; hierarchy adds an embedding-induced task prior.
  super().fit(safe_sequences);vectors=[task_vector(x.task) for x in safe_sequences];self.centers,assign=self.cluster(vectors);self.regime_counts=[Counter() for _ in range(self.regimes)]
  for sequence,regime in zip(safe_sequences,assign):
   for i,event in enumerate(sequence.events):self.regime_counts[regime][transition_signature(sequence.events[i-1] if i else None,event)]+=1
  raw=[self.hierarchical_score(x) for x in safe_sequences];self.calibration=[]
  for regime in range(self.regimes):
   values=[score for score,a in zip(raw,assign) if a==regime];self.calibration.append((mean(values),max(pstdev(values),.03)))
 def hierarchical_score(self,sequence):
  regime=self.regime(sequence.task);counts=self.regime_counts[regime];vocabulary=list(self.signatures);denominator=sum(counts.values())+len(vocabulary);values=[]
  for i,event in enumerate(sequence.events):
   signature=transition_signature(sequence.events[i-1] if i else None,event);probability=(counts[signature]+1)/denominator;values.append(-math.log(probability))
  # Combine regime surprise with continuous intent/DTE alignment.
  return .65*max(values,default=0)+.35*max(self.scores(sequence),default=0)
 def predict(self,sequence):
  score=self.hierarchical_score(sequence);regime=self.regime(sequence.task);center,spread=self.calibration[regime];z=(score-center)/(3*spread);probability=1/(1+math.exp(-max(-20,min(20,z))));return type('HierarchicalPrediction',(),{'deviation_score':score,'boundary_probability':probability,'boundary_present':probability>=.5,'regime':regime})()
