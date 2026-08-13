#!/usr/bin/env python3
"""PIDR-v1: dependency-light linear representation learner for observable prefixes."""
from __future__ import annotations
import hashlib,json,math,random,re
from pathlib import Path

CAPS=['A0_OBSERVE','A1_LOCAL_MODIFY','A2_EXECUTE','A3_PERSISTENT_CHANGE','A4_EXTERNAL_SIDE_EFFECT']
TOKEN=re.compile(r"[A-Za-z0-9_./:-]+")
def stable(token):return int.from_bytes(hashlib.sha256(token.encode()).digest()[:8],'big')
def cosine_distance(a,b):return 1-sum(x*y for x,y in zip(a,b))
class PIDRV1:
 def __init__(self,latent_dim=128,lambda_sep=1.0,beta_temp=.1,gamma_var=.1,margin=.1,target_std=.05,seed=71001):
  self.latent_dim=latent_dim;self.lambda_sep=lambda_sep;self.beta_temp=beta_temp;self.gamma_var=gamma_var;self.margin=margin;self.target_std=target_std;self.seed=seed;self.scales=[1.0]*latent_dim
 def feature_dict(self,sample):
  # Intentionally whitelist observable prefix fields; sampler metadata cannot enter.
  out={};text=' '.join([sample['task'],*sample['previous_actions'],*sample['previous_tools'],*sample['previous_observations'],sample['current_observation'],sample['current_observation_source'],sample['current_action'],sample['current_tool']]).lower();tokens=TOKEN.findall(text)
  for token in tokens:
   out['u:'+token]=out.get('u:'+token,0)+1
  for a,b in zip(tokens,tokens[1:]):out['b:'+a+'|'+b]=out.get('b:'+a+'|'+b,0)+1
  for key in ('paradigm','current_tool','current_observation_source','current_capability','previous_capability'):out[key+':'+str(sample[key])]=1
  out['progress']=sample['normalized_progress'];out['recent_tool_run_length']=sample['recent_tool_run_length']/12;out['recent_action_run_length']=sample['recent_action_run_length']/12
  return out
 def raw(self,sample):
  vector=[0.0]*self.latent_dim
  for key,value in self.feature_dict(sample).items():
   h=stable(key);vector[h%self.latent_dim]+=(1 if (h>>8)&1 else -1)*float(value)
  return vector
 def encode(self,sample,raw=False):
  x=self.raw(sample);z=x if raw else [v*s for v,s in zip(x,self.scales)];norm=math.sqrt(sum(v*v for v in z)) or 1;return [v/norm for v in z]
 def distance(self,a,b,raw=False):return cosine_distance(self.encode(a,raw),self.encode(b,raw))
 def _loss_dims(self,a,b):
  x,y=self.raw(a),self.raw(b);return [(u-v)**2 for u,v in zip(x,y)]
 def fit(self,pre_pairs,post_pairs,temp_pairs,epochs=8,lr=.03):
  # Linear diagonal projection learned by deterministic contrastive multiplicative updates.
  rng=random.Random(self.seed);events=[]
  for _ in range(epochs):
   events=[('pre',*p) for p in pre_pairs]+[('post',*p) for p in post_pairs]+[('temp',*p) for p in temp_pairs];rng.shuffle(events)
   for kind,a,b in events:
    dims=self._loss_dims(a,b);d=sum(s*s*x for s,x in zip(self.scales,dims))/(sum(s*s for s in self.scales)+1e-9)
    weight=1.0 if kind=='pre' else self.beta_temp if kind=='temp' else (-self.lambda_sep if d<self.margin else 0.0)
    for j,x in enumerate(dims):self.scales[j]*=math.exp(max(-.08,min(.08,-lr*weight*(x-d))))
   avg=sum(self.scales)/len(self.scales);self.scales=[max(self.target_std,min(8,s/avg)) for s in self.scales]
  return self
 def latent_variance(self,samples):
  zs=[self.encode(s) for s in samples]
  if not zs:return 0
  vals=[]
  for j in range(self.latent_dim):
   m=sum(z[j] for z in zs)/len(zs);vals.append(math.sqrt(sum((z[j]-m)**2 for z in zs)/len(zs)))
  return sum(vals)/len(vals)
 def to_dict(self,metadata):return {'model':'Paradigm-Invariant Delegation Representation v1','version':'PIDR-v1','architecture':'signed hashed unigram+bigram and structured features; learned linear diagonal projection; L2 normalization','feature_hashing':{'hash':'SHA256 signed hashing','unigrams':True,'bigrams':True,'input_buckets':self.latent_dim},'projection_parameters':{'diagonal_scales':self.scales},'latent_dimension':self.latent_dim,'lambda_sep':self.lambda_sep,'beta_temp':self.beta_temp,'gamma_var':self.gamma_var,'margin':self.margin,'target_std':self.target_std,'seed':self.seed,**metadata}
 @classmethod
 def from_dict(cls,d):
  m=cls(d['latent_dimension'],d['lambda_sep'],d['beta_temp'],d['gamma_var'],d['margin'],d['target_std'],d['seed']);m.scales=d['projection_parameters']['diagonal_scales'];return m
 def save(self,path,metadata):Path(path).write_text(json.dumps(self.to_dict(metadata),indent=2)+'\n')
