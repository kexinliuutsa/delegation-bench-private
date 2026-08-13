#!/usr/bin/env python3
"""Label-free boundary gate from a safe delegation-evolution prior."""
from __future__ import annotations
import bisect,math,re
from collections import Counter,defaultdict
from dataclasses import dataclass
from models.risk_emergence_model import ObservableSequence
DIMENSIONS=('resource_scope','operation_scope','information_scope','persistence_level','external_effect')
def terms(text):return frozenset(re.findall(r'[a-z]+',text.lower()))
def similarity(a,b):return len(a&b)/len(a|b) if a|b else 1.
@dataclass(frozen=True)
class LabelFreeGatePrediction:
 boundary_probability:float
 boundary_present:bool
 step_deviation_scores:tuple[float,...]
 step_boundary_probabilities:tuple[float,...]
class LearnedDelegationPriorGate:
 def __init__(self):self.safe_sequences=[];self.safe_terms=[];self.global_cap=defaultdict(Counter);self.global_dims={d:defaultdict(Counter) for d in DIMENSIONS};self.safe_max_scores=[];self.threshold=math.inf;self.fitted=False
 def fit(self,safe_sequences:list[ObservableSequence]):
  if not safe_sequences:raise ValueError('safe sequences required')
  self.safe_sequences=list(safe_sequences);self.safe_terms=[terms(x.task) for x in safe_sequences]
  for sequence in safe_sequences:
   previous_cap='start';previous_state={d:'none' for d in DIMENSIONS}
   for event in sequence.events:
    self.global_cap[previous_cap][event.capability]+=1
    for d in DIMENSIONS:self.global_dims[d][previous_state[d]][event.delegation_state[d]]+=1
    previous_cap=event.capability;previous_state=event.delegation_state
  maxima=[max(self.deviation_scores(sequence)) for sequence in safe_sequences];self.safe_max_scores=sorted(maxima);index=min(len(maxima)-1,math.ceil(.99*len(maxima))-1);self.threshold=self.safe_max_scores[index]+1e-9;self.fitted=True
 def neighbors(self,task,k=20):
  query=terms(task);ranked=sorted(range(len(self.safe_sequences)),key=lambda i:similarity(query,self.safe_terms[i]),reverse=True);return [self.safe_sequences[i] for i in ranked[:k]]
 @staticmethod
 def smooth(counts:Counter,value,alphabet):return (counts[value]+.5)/(sum(counts.values())+.5*alphabet)
 def deviation_scores(self,sequence:ObservableSequence)->list[float]:
  neighbors=self.neighbors(sequence.task);local_cap=defaultdict(Counter);local_dims={d:defaultdict(Counter) for d in DIMENSIONS}
  for safe in neighbors:
   pc='start';ps={d:'none' for d in DIMENSIONS}
   for event in safe.events:
    local_cap[pc][event.capability]+=1
    for d in DIMENSIONS:local_dims[d][ps[d]][event.delegation_state[d]]+=1
    pc=event.capability;ps=event.delegation_state
  scores=[];pc='start';ps={d:'none' for d in DIMENSIONS}
  for event in sequence.events:
   cap_counts=self.global_cap[pc]+local_cap[pc];probabilities=[self.smooth(cap_counts,event.capability,5)]
   for d in DIMENSIONS:
    counts=self.global_dims[d][ps[d]]+local_dims[d][ps[d]];probabilities.append(self.smooth(counts,event.delegation_state[d],5))
   scores.append(-sum(math.log(max(p,1e-9)) for p in probabilities)/len(probabilities));pc=event.capability;ps=event.delegation_state
  return scores
 def predict(self,sequence:ObservableSequence)->LabelFreeGatePrediction:
  if not self.fitted:raise RuntimeError('model not fitted')
  scores=self.deviation_scores(sequence);probabilities=[]
  for score in scores:
   cdf=(bisect.bisect_left(self.safe_max_scores,score)+1)/(len(self.safe_max_scores)+1);probabilities.append(max(0.,min(1.,(cdf-.95)/.05)))
  maximum=max(scores);boundary_probability=max(probabilities);return LabelFreeGatePrediction(boundary_probability,maximum>self.threshold,tuple(scores),tuple(probabilities))
