#!/usr/bin/env python3
"""Evaluate DTF on the sealed seed-2 paired holdout."""
from __future__ import annotations
import argparse,csv,json,math,re,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.authority_source_alignment import align
from models.delegation_transition_factor import DelegationTransitionFactorModel,factors
def parse(path):return re.match(r"(.+)_(control|treatment)\.json$",path.name).groups()
def percentile(values,q):values=sorted(values);return values[max(0,min(len(values)-1,math.ceil(q*len(values))-1))]
def divergence(c,t):return {x["treatment_step"] for x in align(c["steps"],t["steps"]) if x.get("treatment_step") and x["relation"] in {"NEW","MODIFIED"}}
def auroc(truth,scores):
 positives=[x for y,x in zip(truth,scores) if y];negatives=[x for y,x in zip(truth,scores) if not y];return sum(1 if a>b else .5 if a==b else 0 for a in positives for b in negatives)/(len(positives)*len(negatives))
def main():
 p=argparse.ArgumentParser();base=ROOT/"results/environment_influence_expansion";p.add_argument("--raw-dir",type=Path,default=base/"raw");p.add_argument("--output-dir",type=Path,default=base/"delegation_transition_factor");a=p.parse_args();pairs=defaultdict(dict)
 for path in a.raw_dir.glob("*.json"):pair,role=parse(path);pairs[pair][role]=json.loads(path.read_text())
 development={k:v for k,v in pairs.items() if not k.endswith("_s02")};holdout={k:v for k,v in pairs.items() if k.endswith("_s02")};controls=[x["control"] for x in development.values()];model=DelegationTransitionFactorModel().fit(controls);model.threshold=percentile([max(model.score_trajectory(x)) for x in controls],.95);truth=[];scores=[];false=[];detected=[];step_rows=[]
 for pair,roles in sorted(holdout.items()):
  diff=divergence(roles["control"],roles["treatment"]);role_scores={role:model.score_trajectory(value) for role,value in roles.items()};false.append(any(x>model.threshold for x in role_scores["control"]));alarms=[i for i,x in enumerate(role_scores["treatment"],1) if x>model.threshold];detected.append(bool(diff and any(i in diff for i in alarms)))
  for role,trajectory in roles.items():
   previous=None
   for event,score in zip(trajectory["steps"],role_scores[role]):
    row=factors(trajectory["task"],event,previous);target=role=="treatment" and event["step"] in diff;truth.append(target);scores.append(score);step_rows.append({"pair_id":pair,"trajectory_role":role,"step":event["step"],"capability_delta":row[0],"persistence_delta":row[1],"externality_delta":row[2],"task_alignment_delta":round(row[3],6),"factor_transition_score":round(score,6),"alarm":score>model.threshold,"counterfactual_divergence_proxy":target});previous=event
 result={"holdout_pairs":len(holdout),"auroc":round(auroc(truth,scores),4),"false_alarm":round(mean(false),4),"pair_detection":round(mean(detected),4),"threshold":round(model.threshold,6),"training":"seed 0/1 controls only","evaluation":"seed 2 paired holdout","manual_source_attack_risk_labels_used":False};a.output_dir.mkdir(parents=True,exist_ok=True);model.save(a.output_dir/"delegation_transition_factor.json")
 with (a.output_dir/"dtf_step_scores.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(step_rows[0]));w.writeheader();w.writerows(step_rows)
 (a.output_dir/"dtf_summary.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
