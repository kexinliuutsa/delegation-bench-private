#!/usr/bin/env python3
"""PIDR: a small contrastive paradigm-invariant delegation representation."""
from __future__ import annotations
import hashlib,json,math,random,re
from pathlib import Path
from experiments.multi_agent_delegation_benchmark import CAPABILITY_LEVEL,capability_state

def _add(vector,key,value=1.0):
 digest=hashlib.blake2b(key.encode(),digest_size=8).digest();number=int.from_bytes(digest,'big');vector[number%len(vector)]+=value if (number>>8)&1 else -value
def vectorize(trajectory,event,index,dimensions=96):
 values=[0.0]*dimensions;steps=trajectory['steps'];progress=min(4,int(5*index/max(1,len(steps))));state=capability_state(event,trajectory.get('agent_type','coding'));level=CAPABILITY_LEVEL[state];previous=CAPABILITY_LEVEL[capability_state(steps[index-1],trajectory.get('agent_type','coding'))] if index else 0
 for feature in (f'shared:progress={progress}',f'shared:level={level}',f'shared:delta={level-previous}',f'shared:source={str(event.get("observation_source","unknown")).lower()}'): _add(values,feature,2.0)
 for section,text in (('task',trajectory.get('task','')),('action',event.get('action','')),('observation',event.get('observation','')),('tool',event.get('tool',''))):
  for token in re.findall(r'[a-z0-9_.+/-]+',str(text).lower()):_add(values,f'{section}:{token}',.35)
 norm=math.sqrt(sum(x*x for x in values)) or 1.0;return [x/norm for x in values]
def euclidean(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b))/len(a))

class ParadigmInvariantDelegationRepresentation:
 def __init__(self,input_dim=96,latent_dim=24,margin=.45,seed=63):
  self.input_dim=input_dim;self.latent_dim=latent_dim;self.margin=margin;r=random.Random(seed);self.weights=[[r.gauss(0,1/math.sqrt(input_dim)) for _ in range(input_dim)] for _ in range(latent_dim)]
 def encode_vector(self,x):return [sum(w*v for w,v in zip(row,x)) for row in self.weights]
 def encode_step(self,trajectory,index):return self.encode_vector(vectorize(trajectory,trajectory['steps'][index],index,self.input_dim))
 def fit(self,positive_pairs,negative_pairs,epochs=160,rate=.035):
  examples=[(1,a,b) for a,b in positive_pairs]+[(0,a,b) for a,b in negative_pairs];rng=random.Random(6301)
  for epoch in range(epochs):
   rng.shuffle(examples);eta=rate/(1+.01*epoch)
   for positive,left,right in examples:
    delta=[a-b for a,b in zip(left,right)];projected=[sum(w*v for w,v in zip(row,delta)) for row in self.weights];distance=math.sqrt(sum(x*x for x in projected)/self.latent_dim)+1e-9
    if positive:coefficient=2.0/self.latent_dim
    elif distance<self.margin:coefficient=-2*(self.margin-distance)/(distance*self.latent_dim)
    else:continue
    for j,row in enumerate(self.weights):
     factor=coefficient*projected[j]
     for i,value in enumerate(delta):row[i]-=eta*(factor*value+1e-4*row[i])
  return self
 def distance(self,left,right):return euclidean(self.encode_vector(left),self.encode_vector(right))
 def save(self,path):
  Path(path).write_text(json.dumps({'model':'PIDR','version':'pidr-poc-v1','input_dim':self.input_dim,'latent_dim':self.latent_dim,'margin':self.margin,'weights':self.weights,'objective':'benign cross-paradigm alignment plus paired intervention margin separation','unsafe_or_authority_labels_used':False},indent=2)+'\n')
 @classmethod
 def load(cls,path):
  value=json.loads(Path(path).read_text());model=cls(value['input_dim'],value['latent_dim'],value['margin']);model.weights=value['weights'];return model
