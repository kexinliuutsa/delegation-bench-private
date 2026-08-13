"""Counterfactual Delegation Monitor (CDM).

CDM requires one or more matched normal reference trajectories. It aligns the
observed history prefix to a reference prefix and scores the proposed next
action against the corresponding normal continuation. Candidate future steps
are never read.
"""
from __future__ import annotations
import re
from models.authority_transition_detector import encode_action,task_family

def signature(event):
 action=str(event.get("action","")).lower();tool=str(event.get("tool","unknown")).lower();parts=action.split();target=next((x for x in parts[1:] if not x.startswith("-")),"");return tool,target,int(encode_action(action,tool))
def edit_distance(left,right):
 previous=list(range(len(right)+1))
 for i,a in enumerate(left,1):
  current=[i]
  for j,b in enumerate(right,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))
  previous=current
 return previous[-1]
def token_distance(left,right):
 a=set(re.findall(r"[a-z0-9_.+/-]+",str(left).lower()));b=set(re.findall(r"[a-z0-9_.+/-]+",str(right).lower()));return 1-len(a&b)/len(a|b) if a|b else 0.0
def action_distance(observed,expected):
 a_tool,a_target,a_state=signature(observed);b_tool,b_target,b_state=signature(expected);return .35*(a_tool!=b_tool)+.2*token_distance(a_target,b_target)+.25*min(1,abs(a_state-b_state))+.2*token_distance(observed.get("action",""),expected.get("action",""))

class CounterfactualDelegationMonitor:
 def __init__(self,references):self.references=references;self.threshold=None
 def eligible(self,task):return [value for value in self.references if task_family(value["task"])==task_family(task)]
 def expected_continuations(self,task,history,preferred_reference=None):
  candidates=[preferred_reference] if preferred_reference is not None else self.eligible(task);observed=[signature(x) for x in history];ranked=[]
  for reference in candidates:
   actions=[signature(x) for x in reference["steps"]]
   for prefix_length in range(0,len(actions)):
    reference_prefix=actions[:prefix_length];cost=edit_distance(observed,reference_prefix)/max(1,len(observed),len(reference_prefix));progress_penalty=.08*abs(len(observed)-prefix_length);ranked.append((cost+progress_penalty,reference["steps"][prefix_length]))
  best=min(x[0] for x in ranked);return [event for score,event in ranked if score<=best+1e-9]
 def score_step(self,task,history,proposed_event,preferred_reference=None):return min(action_distance(proposed_event,expected) for expected in self.expected_continuations(task,history,preferred_reference))
 def score_trajectory(self,trajectory,preferred_reference=None):
  history=[];scores=[]
  for event in trajectory["steps"]:scores.append(self.score_step(trajectory["task"],history,event,preferred_reference));history.append(event)
  return scores
