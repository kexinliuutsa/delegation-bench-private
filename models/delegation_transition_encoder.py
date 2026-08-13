#!/usr/bin/env python3
"""Contrastive Delegation Transition Encoder over observable state changes."""
from __future__ import annotations
import hashlib,math,random,re
from dataclasses import dataclass
from models.risk_emergence_model import ObservableEvent

DIMENSIONS=('resource_scope','operation_scope','information_scope','persistence_level','external_effect')
INPUT_DIM=384
LATENT_DIM=24

def _tokens(task:str,previous:ObservableEvent|None,current:ObservableEvent)->list[str]:
 def words(text):return re.findall(r'[a-z0-9]+',text.lower())
 values=[f'task:{x}' for x in words(task)]+[f'action:{x}' for x in words(current.action)]+[f'observation:{x}' for x in words(current.observation)]+[f'capability:{current.capability}']
 before=previous.delegation_state if previous else {key:'none' for key in DIMENSIONS}
 for key in DIMENSIONS:
  values += [f'before:{key}={before[key]}',f'after:{key}={current.delegation_state[key]}',f'edge:{key}:{before[key]}->{current.delegation_state[key]}']
 return values

def transition_signature(previous:ObservableEvent|None,current:ObservableEvent)->tuple[str,...]:
 before=previous.delegation_state if previous else {key:'none' for key in DIMENSIONS}
 return tuple(f'{key}:{before[key]}->{current.delegation_state[key]}' for key in DIMENSIONS if before[key]!=current.delegation_state[key]) or ('no_change',)

def _vector(tokens:list[str])->list[float]:
 output=[0.0]*INPUT_DIM
 for token in tokens:
  digest=hashlib.blake2b(token.encode(),digest_size=8).digest();value=int.from_bytes(digest,'big');output[value%INPUT_DIM]+=1 if value>>63 else -1
 norm=math.sqrt(sum(x*x for x in output));return [x/norm for x in output] if norm else output

@dataclass(frozen=True)
class TransitionExample:
 task:str
 previous:ObservableEvent|None
 current:ObservableEvent

class DelegationTransitionEncoder:
 def __init__(self):
  rng=random.Random(3801);self.weights=[[rng.uniform(-.08,.08) for _ in range(INPUT_DIM)] for _ in range(LATENT_DIM)];self.fitted=False
 def raw(self,x:TransitionExample):return _vector(_tokens(x.task,x.previous,x.current))
 def encode_raw(self,value):
  z=[sum(w*x for w,x in zip(row,value)) for row in self.weights];norm=math.sqrt(sum(x*x for x in z));return tuple(x/norm for x in z) if norm else tuple(z)
 def encode(self,x:TransitionExample):return self.encode_raw(self.raw(x))
 def fit(self,examples:list[TransitionExample])->None:
  raw=[self.raw(x) for x in examples];signatures=[transition_signature(x.previous,x.current) for x in examples];pairs=[]
  for i in range(len(examples)):
   positives=[j for j in range(len(examples)) if i!=j and signatures[i]==signatures[j]];negatives=[j for j in range(len(examples)) if signatures[i]!=signatures[j]]
   if positives and negatives:pairs.append((i,positives[i%len(positives)],1));pairs.append((i,negatives[i%len(negatives)],-1))
  for epoch in range(18):
   random.Random(3900+epoch).shuffle(pairs);rate=.025/math.sqrt(epoch+1)
   for i,j,target in pairs:
    a,b=raw[i],raw[j];za=self.encode_raw(a);zb=self.encode_raw(b);similarity=sum(x*y for x,y in zip(za,zb));gradient=(similarity-(1.0 if target==1 else -0.25))
    for d in range(LATENT_DIM):
     for f,(av,bv) in enumerate(zip(a,b)):
      if av or bv:self.weights[d][f]-=rate*gradient*(zb[d]*av+za[d]*bv)
  self.fitted=True

def cosine(a,b):return sum(x*y for x,y in zip(a,b))
