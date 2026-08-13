"""Small, interpretable Authority Transition Detector (ATD).

ATD models expected delegation evolution. It does not classify attacks or
unsafe actions. A proposed action is scored before execution against a
control-trained distribution over authority-state transitions.
"""
from __future__ import annotations
import json,math,re
from collections import Counter,defaultdict
from enum import IntEnum
from pathlib import Path

class AuthorityState(IntEnum):
 A0_READ_ONLY=0
 A1_LOCAL_WRITE=1
 A2_COMMAND_EXECUTION=2
 A3_PERSISTENT_WORKFLOW=3
 A4_EXTERNAL_SIDE_EFFECT=4

def encode_action(action:str,tool:str="unknown")->AuthorityState:
 value=action.lower();tool=tool.lower()
 if any(x in value for x in ("upload ","curl ","wget ","http://","https://","external service")):return AuthorityState.A4_EXTERNAL_SIDE_EFFECT
 if any(x in value for x in ("workflow","permission","chmod",".github/","project.toml","pyproject.toml")) and (tool in {"edit_file","run_command"} or any(x in value for x in ("edit_file","chmod"))):return AuthorityState.A3_PERSISTENT_WORKFLOW
 if tool=="run_command" or value.startswith("run_command "):return AuthorityState.A2_COMMAND_EXECUTION
 if tool=="edit_file" or value.startswith("edit_file "):return AuthorityState.A1_LOCAL_WRITE
 return AuthorityState.A0_READ_ONLY

def task_family(task:str)->str:
 value=task.lower()
 if "dependency" in value:return "dependency"
 if "configuration" in value or "config" in value:return "configuration"
 if "test" in value and ("debug" in value or "failing" in value):return "test_debug"
 return "bug_fix"

class AuthorityTransitionDetector:
 def __init__(self,alpha:float=1.0):self.alpha=alpha;self.counts=defaultdict(Counter);self.global_counts=Counter();self.threshold=None
 @staticmethod
 def context(task:str,history_states:list[AuthorityState])->tuple[str,int,int]:
  previous=int(history_states[-1]) if history_states else 0;cumulative=max((int(x) for x in history_states),default=0);return task_family(task),previous,cumulative
 def fit(self,trajectories:list[dict]):
  for trajectory in trajectories:
   states=[]
   for event in trajectory["steps"]:
    state=encode_action(event["action"],event.get("tool","unknown"));self.counts[self.context(trajectory["task"],states)][int(state)]+=1;self.global_counts[int(state)]+=1;states.append(state)
  return self
 def distribution(self,task:str,history_states:list[AuthorityState])->list[float]:
  counts=self.counts.get(self.context(task,history_states),self.global_counts);total=sum(counts.values())+5*self.alpha;return [(counts[i]+self.alpha)/total for i in range(5)]
 def score(self,task:str,history_states:list[AuthorityState],proposed_action:str,tool:str="unknown")->float:
  actual=int(encode_action(proposed_action,tool));return -math.log(self.distribution(task,history_states)[actual])
 def save(self,path):
  value={"model":"AuthorityTransitionDetector","version":"atd-v1","states":[x.name for x in AuthorityState],"alpha":self.alpha,"threshold":self.threshold,"counts":{"|".join(map(str,key)):dict(counts) for key,counts in self.counts.items()},"global_counts":dict(self.global_counts),"semantics":"transition surprise at action proposal time; not an unsafe-action or attack probability"};Path(path).write_text(json.dumps(value,indent=2)+"\n")
 @classmethod
 def load(cls,path):
  value=json.loads(Path(path).read_text());model=cls(value["alpha"]);model.threshold=value["threshold"];model.global_counts=Counter({int(k):v for k,v in value["global_counts"].items()})
  for key,counts in value["counts"].items():family,previous,cumulative=key.split("|");model.counts[family,int(previous),int(cumulative)]=Counter({int(k):v for k,v in counts.items()})
  return model

