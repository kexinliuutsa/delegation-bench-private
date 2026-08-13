"""Context-conditioned Normal Delegation Transition Retrieval (C-NDTR)."""
from __future__ import annotations
from collections import defaultdict
from models.latent_delegation_transition import NormalDelegationTransitionRetrieval,distance
from models.authority_transition_detector import task_family

def phase(previous_step_count):
 if previous_step_count<=2:return "early"
 if previous_step_count<=6:return "middle"
 return "late"
def tool_state(tool):
 value=str(tool or "unknown").lower()
 if value in {"read_file","list_files","search_text"}:return "inspect"
 if value=="edit_file":return "modify"
 if value=="run_command":return "execute"
 if value=="finish":return "finish"
 return "other"

class ContextualNDTR(NormalDelegationTransitionRetrieval):
 def __init__(self,dimensions=128,history_window=5,neighbors=15,min_bucket=3):
  super().__init__(dimensions,history_window,neighbors);self.min_bucket=min_bucket;self.context_memory=defaultdict(list)
 def fit(self,trajectories,contrastive=False):
  super().fit(trajectories,contrastive=contrastive)
  self.context_memory=defaultdict(list)
  for trajectory in trajectories:
   family=task_family(trajectory["task"]);previous=[];latents=[]
   for event in trajectory["steps"]:
    latents.append(self.project(self.encoder.encode(trajectory["task"],previous,event["observation"],event["action"])));previous.append(event["action"])
   for index,(left,right) in enumerate(zip(latents,latents[1:])):
    prior=trajectory["steps"][index];record=(left,right);self.context_memory[family,phase(index+1),tool_state(prior.get("tool"))].append(record);self.context_memory[family,phase(index+1),"*"].append(record)
  return self
 def expected(self,task,previous_latent,previous_step_count,previous_tool):
  family=task_family(task);keys=((family,phase(previous_step_count),tool_state(previous_tool)),(family,phase(previous_step_count),"*"));candidates=[]
  for key in keys:
   if len(self.context_memory[key])>=self.min_bucket:candidates=self.context_memory[key];break
  if not candidates:candidates=self.transitions[family]
  nearest=sorted(((distance(previous_latent,left),right) for left,right in candidates),key=lambda x:x[0])[:self.neighbors];weights=[1/(value+1e-4) for value,_ in nearest];total=sum(weights);return [sum(weight*row[i] for weight,(_,row) in zip(weights,nearest))/total for i in range(len(previous_latent))]
 def score_trajectory(self,trajectory):
  previous_actions=[];previous_latent=None;scores=[];previous_tool="unknown"
  for event in trajectory["steps"]:
   observed=self.project(self.encoder.encode(trajectory["task"],previous_actions,event["observation"],event["action"]));predicted=self.initial[task_family(trajectory["task"])] if previous_latent is None else self.expected(trajectory["task"],previous_latent,len(previous_actions),previous_tool);score=(sum(((a-b)/s)**2 for a,b,s in zip(observed,predicted,self.residual_scales))/len(observed))**.5;scores.append(score);previous_latent=observed;previous_actions.append(event["action"]);previous_tool=event.get("tool","unknown")
  return scores
