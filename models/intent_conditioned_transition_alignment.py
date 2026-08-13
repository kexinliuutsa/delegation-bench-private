#!/usr/bin/env python3
"""Safe-only task-conditioned transition alignment model."""
from __future__ import annotations
import math,re
from collections import Counter,defaultdict
from dataclasses import dataclass
from models.delegation_transition_encoder import DelegationTransitionEncoder,TransitionExample,cosine,transition_signature
from models.risk_emergence_model import ObservableSequence

def words(text):return set(re.findall(r'[a-z0-9]+',text.lower()))
@dataclass(frozen=True)
class AlignmentPrediction:
 deviation_scores:tuple[float,...]
 boundary_probability:float
 boundary_present:bool

class IntentConditionedTransitionAlignment:
 def __init__(self):self.encoder=DelegationTransitionEncoder();self.word_signature=defaultdict(Counter);self.signatures=Counter();self.centroids={};self.threshold=0.;self.fitted=False
 def examples(self,sequence):return [TransitionExample(sequence.task,sequence.events[i-1] if i else None,event) for i,event in enumerate(sequence.events)]
 def fit(self,safe_sequences:list[ObservableSequence])->None:
  transitions=[]
  for sequence in safe_sequences:
   for example in self.examples(sequence):
    signature=transition_signature(example.previous,example.current);self.signatures[signature]+=1;transitions.append(example)
    for word in words(sequence.task):self.word_signature[word][signature]+=1
  self.encoder.fit(transitions)
  grouped=defaultdict(list)
  for example in transitions:grouped[transition_signature(example.previous,example.current)].append(self.encoder.encode(example))
  for signature,vectors in grouped.items():
   center=[sum(values)/len(values) for values in zip(*vectors)];norm=math.sqrt(sum(x*x for x in center));self.centroids[signature]=tuple(x/norm for x in center)
  calibration=[max(self.scores(sequence),default=0.) for sequence in safe_sequences];ordered=sorted(calibration);self.threshold=ordered[min(len(ordered)-1,int(.99*len(ordered)))] + 1e-9;self.fitted=True
 def scores(self,sequence):
  vocabulary=list(self.signatures);total=sum(self.signatures.values());output=[]
  for example in self.examples(sequence):
   task_words=words(sequence.task);counts=Counter(self.signatures)
   for word in task_words:counts.update(self.word_signature.get(word,{}))
   denominator=sum(counts.values())+len(vocabulary);priors={sig:(counts[sig]+1)/denominator for sig in vocabulary};z=self.encoder.encode(example);kernels={sig:math.exp(5*cosine(z,self.centroids[sig])) for sig in vocabulary};kernel_total=sum(kernels.values());probability=sum(priors[sig]*kernels[sig]/kernel_total for sig in vocabulary)
   # NLL combines the task-conditioned safe prior with latent DTE alignment.
   output.append(-math.log(probability))
  return output
 def predict(self,sequence):
  if not self.fitted:raise RuntimeError('model not fitted')
  scores=tuple(self.scores(sequence));maximum=max(scores,default=0.);scale=max(self.threshold,1e-6);probability=1/(1+math.exp(-4*(maximum/scale-1)));return AlignmentPrediction(scores,probability,maximum>self.threshold)
