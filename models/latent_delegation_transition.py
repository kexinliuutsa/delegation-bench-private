"""Latent Delegation Transition Detector (LDTD), without safety labels."""
from __future__ import annotations
import hashlib,json,math,re
from collections import defaultdict
from pathlib import Path
from models.authority_transition_detector import encode_action,task_family

def _tokens(text):
 words=re.findall(r"[a-z0-9_.+/-]+",text.lower());return words+[f"{a}::{b}" for a,b in zip(words,words[1:])]

class HashedTrajectoryEncoder:
 def __init__(self,dimensions=128,history_window=4):self.dimensions=dimensions;self.history_window=history_window
 def encode(self,task,previous_actions,current_observation,current_action):
  history=previous_actions if self.history_window is None else previous_actions[-self.history_window:];sections=(("task",task),("history"," ".join(history)),("observation",current_observation),("action",current_action));values=[0.0]*self.dimensions
  for section,text in sections:
   for token in _tokens(str(text)):
    digest=hashlib.blake2b(f"{section}:{token}".encode(),digest_size=8).digest();number=int.from_bytes(digest,"big");index=number%self.dimensions;values[index]+=1 if (number>>8)&1 else -1
  norm=math.sqrt(sum(x*x for x in values)) or 1;return [x/norm for x in values]

def distance(left,right):return math.sqrt(sum((a-b)**2 for a,b in zip(left,right))/len(left))

class LatentDelegationTransitionDetector:
 def __init__(self,dimensions=128,history_window=4,neighbors=5):self.encoder=HashedTrajectoryEncoder(dimensions,history_window);self.neighbors=neighbors;self.weights=[1.0]*dimensions;self.initial={};self.deltas={};self.transitions=defaultdict(list);self.transition_records=defaultdict(list);self.residual_scales=[1.0]*dimensions;self.threshold=None
 def project(self,vector):return [math.sqrt(w)*x for w,x in zip(self.weights,vector)]
 def learn_contrastive_metric(self,examples,epochs=30,margin=.8,rate=.015):
  by_task_stage=defaultdict(list);by_stage=defaultdict(list)
  for item in examples:by_task_stage[item["task_family"],item["stage"]].append(item);by_stage[item["stage"]].append(item)
  positives=[]
  for values in by_task_stage.values():
   seeds=defaultdict(list)
   for item in values:seeds[item["seed"]].append(item)
   keys=sorted(seeds)
   for a,b in zip(keys,keys[1:]):positives.append((seeds[a][0]["x"],seeds[b][0]["x"]))
  negatives=[];stages=sorted(by_stage)
  for a,b in zip(stages,stages[1:]):
   for left,right in zip(by_stage[a][:80],by_stage[b][:80]):negatives.append((left["x"],right["x"]))
  for _ in range(epochs):
   gradients=[0.0]*len(self.weights)
   for left,right in positives:
    for i,(a,b) in enumerate(zip(left,right)):gradients[i]+=(a-b)**2/max(1,len(positives))
   for left,right in negatives:
    squared=sum(w*(a-b)**2 for w,a,b in zip(self.weights,left,right))
    if squared<margin*margin:
     for i,(a,b) in enumerate(zip(left,right)):gradients[i]-=(a-b)**2/max(1,len(negatives))
   for i in range(len(self.weights)):self.weights[i]=max(.02,min(8.0,self.weights[i]-rate*(gradients[i]+.01*(self.weights[i]-1))))
  scale=sum(self.weights)/len(self.weights);self.weights=[x/scale for x in self.weights]
 def fit(self,trajectories,contrastive=True):
  examples=[];sequences=[]
  for trajectory in trajectories:
   previous=[];sequence=[]
   for event in trajectory["steps"]:
    x=self.encoder.encode(trajectory["task"],previous,event["observation"],event["action"]);examples.append({"task_family":task_family(trajectory["task"]),"stage":int(encode_action(event["action"],event.get("tool","unknown"))),"seed":trajectory["seed"],"x":x});sequence.append(x);previous.append(event["action"])
   sequences.append((task_family(trajectory["task"]),sequence))
  if contrastive:self.learn_contrastive_metric(examples)
  projected=[(family,[self.project(x) for x in seq]) for family,seq in sequences];initial=defaultdict(list);deltas=defaultdict(list)
  for trajectory,(family,seq) in zip(trajectories,projected):
   initial[family].append(seq[0])
   for index,(left,right) in enumerate(zip(seq,seq[1:])):
    deltas[family].append([b-a for a,b in zip(left,right)]);self.transitions[family].append((left,right));self.transition_records[family].append({"left":left,"right":right,"previous_action":trajectory["steps"][index]["action"],"next_action":trajectory["steps"][index+1]["action"],"previous_tool":trajectory["steps"][index].get("tool","unknown"),"next_tool":trajectory["steps"][index+1].get("tool","unknown")})
  average=lambda rows:[sum(row[i] for row in rows)/len(rows) for i in range(len(self.weights))]
  self.initial={key:average(rows) for key,rows in initial.items()};self.deltas={key:average(rows) for key,rows in deltas.items()};residuals=[]
  for family,seq in projected:
   for index,z in enumerate(seq):pred=self.initial[family] if index==0 else [a+b for a,b in zip(seq[index-1],self.deltas[family])];residuals.append([a-b for a,b in zip(z,pred)])
  self.residual_scales=[max(.03,math.sqrt(sum(row[i]**2 for row in residuals)/len(residuals))) for i in range(len(self.weights))];return self
 def predict_next(self,family,previous_latent):
  candidates=sorted(((distance(previous_latent,left),right) for left,right in self.transitions[family]),key=lambda x:x[0])[:self.neighbors];weights=[1/(value+1e-4) for value,_ in candidates];total=sum(weights);return [sum(weight*row[i] for weight,(_,row) in zip(weights,candidates))/total for i in range(len(previous_latent))]
 def score_step(self,task,previous_actions,current_observation,current_action,previous_latent=None):
  family=task_family(task);observed=self.project(self.encoder.encode(task,previous_actions,current_observation,current_action));predicted=self.initial[family] if previous_latent is None else self.predict_next(family,previous_latent);score=math.sqrt(sum(((a-b)/s)**2 for a,b,s in zip(observed,predicted,self.residual_scales))/len(observed));return score,observed
 def score_trajectory(self,trajectory):
  previous=[];latent=None;scores=[]
  for event in trajectory["steps"]:score,latent=self.score_step(trajectory["task"],previous,event["observation"],event["action"],latent);scores.append(score);previous.append(event["action"])
  return scores
 def explain_transition(self,task,previous_latent,observed_latent,previous_action,current_action):
  family=task_family(task);observed_delta=[b-a for a,b in zip(previous_latent,observed_latent)];observed_norm=math.sqrt(sum(x*x for x in observed_delta)) or 1
  best=None
  for record in self.transition_records[family]:
   normal_delta=[b-a for a,b in zip(record["left"],record["right"])];normal_norm=math.sqrt(sum(x*x for x in normal_delta)) or 1;similarity=sum(a*b for a,b in zip(observed_delta,normal_delta))/(observed_norm*normal_norm)
   if best is None or similarity>best[0]:best=(similarity,record)
  similarity,record=best;observed_state=encode_action(current_action).name;normal_state=encode_action(record["next_action"],record["next_tool"]).name
  reason="unexpected authority capability" if observed_state!=normal_state else "unexpected transition within the same authority capability"
  return {"observed_transition":{"from":previous_action,"to":current_action,"authority_state":observed_state},"closest_normal_transition":{"from":record["previous_action"],"to":record["next_action"],"authority_state":normal_state},"cosine_similarity":similarity,"deviation_evidence":reason}
 def save(self,path):
  Path(path).write_text(json.dumps({"model":"LatentDelegationTransitionDetector","version":"ldtd-v2-evidence","encoder":"signed hashed token/bigram trajectory encoder","dimensions":self.encoder.dimensions,"history_window":self.encoder.history_window,"neighbors":self.neighbors,"contrastive_projection":"learned diagonal metric","transition_predictor":f"{self.neighbors}-nearest normal latent transitions","weights":self.weights,"initial":self.initial,"deltas":self.deltas,"transitions":self.transitions,"transition_records":self.transition_records,"residual_scales":self.residual_scales,"threshold":self.threshold,"safety_labels_used":False,"manual_authority_state_used_at_inference":False},indent=2)+"\n")
 @classmethod
 def load(cls,path):
  value=json.loads(Path(path).read_text());model=cls(value["dimensions"],value.get("history_window",4),value.get("neighbors",5));model.weights=value["weights"];model.initial=value["initial"];model.deltas=value["deltas"];model.residual_scales=value["residual_scales"];model.threshold=value["threshold"]
  for family,rows in value["transitions"].items():model.transitions[family]=[(left,right) for left,right in rows]
  for family,rows in value.get("transition_records",{}).items():model.transition_records[family]=rows
  return model

# Paper-facing alias: experiments showed that normal-transition retrieval, not
# contrastive latent learning, is the effective component.
NormalDelegationTransitionRetrieval = LatentDelegationTransitionDetector
