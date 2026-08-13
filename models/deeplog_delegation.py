"""Dependency-light DeepLog-style next-event predictor (smoothed recurrent history table)."""
import math
class DeepLogDelegation:
 def __init__(self,history=5,smoothing=.1,embedding_dim=32,hidden_dim=64):self.history=history;self.smoothing=smoothing;self.embedding_dim=embedding_dim;self.hidden_dim=hidden_dim;self.counts={};self.vocab=set()
 def fit(self,sequences):
  for seq in sequences:
   self.vocab.update(seq)
   for i,x in enumerate(seq):
    h=tuple(seq[max(0,i-self.history):i]);self.counts.setdefault(h,{});self.counts[h][x]=self.counts[h].get(x,0)+1
  return self
 def scores(self,seq):
  out=[];v=max(1,len(self.vocab))
  for i,x in enumerate(seq):
   h=tuple(seq[max(0,i-self.history):i]);c=self.counts.get(h,{});out.append(-math.log((c.get(x,0)+self.smoothing)/(sum(c.values())+self.smoothing*v)))
  return out
