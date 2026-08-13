#!/usr/bin/env python3
"""Joint temporal-attribution decoder over (step, reason) boundaries."""
from __future__ import annotations
import math,random
from dataclasses import dataclass
from models.delegation_boundary_attribution_model import ATTRIBUTIONS
from models.risk_emergence_model import FEATURES,HashedSequenceEncoder,ObservableSequence
CLASSES=('none',*ATTRIBUTIONS)
@dataclass(frozen=True)
class JointBoundaryPrediction:
 step_reason_probabilities:tuple[dict[str,float],...]
 onset_distribution:tuple[float,...]
 no_boundary_probability:float
class SoftmaxHead:
 def __init__(self):self.weights=[[0.0]*FEATURES for _ in CLASSES];self.bias=[0.0]*len(CLASSES)
 def probabilities(self,vector):
  logits=[self.bias[c]+sum(w*x for w,x in zip(self.weights[c],vector)) for c in range(len(CLASSES))];maximum=max(logits);values=[math.exp(x-maximum) for x in logits];total=sum(values);return [x/total for x in values]
 def fit(self,vectors,labels):
  counts=[max(1,labels.count(c)) for c in range(len(CLASSES))];largest=max(counts);class_weights=[min(12.0,largest/count) for count in counts];order=list(range(len(labels)))
  for epoch in range(55):
   random.Random(8201+epoch).shuffle(order);rate=.07/math.sqrt(epoch+1)
   for index in order:
    vector=vectors[index];truth=labels[index];prob=self.probabilities(vector);weight=class_weights[truth]
    for c in range(len(CLASSES)):
     gradient=(prob[c]-int(c==truth))*weight;self.bias[c]-=rate*gradient
     for f,value in enumerate(vector):
      if value:self.weights[c][f]-=rate*(gradient*value+1e-4*self.weights[c][f])
class JointTemporalAttributionDecoder:
 def __init__(self):self.encoder=HashedSequenceEncoder();self.head=SoftmaxHead();self.fitted=False
 def fit(self,sequences:list[ObservableSequence],boundary_steps:list[int|None],attributions:list[str|None]):
  vectors=[];labels=[]
  for sequence,boundary,reason in zip(sequences,boundary_steps,attributions):
   encoded=self.encoder.encode(sequence);vectors.extend(encoded)
   for step in range(1,len(encoded)+1):labels.append(CLASSES.index(reason) if step==boundary and reason in ATTRIBUTIONS else 0)
  self.head.fit(vectors,labels);self.fitted=True
 def predict(self,sequence:ObservableSequence)->JointBoundaryPrediction:
  if not self.fitted:raise RuntimeError('model not fitted')
  local=[]
  for vector in self.encoder.encode(sequence):
   values=self.head.probabilities(vector);local.append({name:values[index+1] for index,name in enumerate(ATTRIBUTIONS)}|{'none':values[0]})
  survival=1.0;joint=[];onset=[]
  for values in local:
   masses={name:survival*values[name] for name in ATTRIBUTIONS};joint.append(masses);onset.append(sum(masses.values()));survival*=values['none']
  total=sum(onset)+survival
  return JointBoundaryPrediction(tuple({name:value/total for name,value in masses.items()} for masses in joint),tuple(value/total for value in onset),survival/total)
 def decode(self,prediction:JointBoundaryPrediction)->tuple[int,str]|None:
  candidates=[(value,step,name) for step,values in enumerate(prediction.step_reason_probabilities,1) for name,value in values.items()]
  value,step,name=max(candidates)
  return None if prediction.no_boundary_probability>value else (step,name)
