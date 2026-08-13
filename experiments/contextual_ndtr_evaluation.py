#!/usr/bin/env python3
"""Compare NDTR and C-NDTR on the sealed seed-2 holdout."""
from __future__ import annotations
import argparse,csv,json,math,re,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.authority_source_alignment import align
from models.latent_delegation_transition import NormalDelegationTransitionRetrieval
from models.contextual_ndtr import ContextualNDTR
def parse(path):return re.match(r"(.+)_(control|treatment)\.json$",path.name).groups()
def percentile(values,q):values=sorted(values);return values[max(0,min(len(values)-1,math.ceil(q*len(values))-1))]
def divergence(c,t):return {x["treatment_step"] for x in align(c["steps"],t["steps"]) if x.get("treatment_step") and x["relation"] in {"NEW","MODIFIED"}}
def auroc(y,s):
 p=[v for a,v in zip(y,s) if a];n=[v for a,v in zip(y,s) if not a];return sum(1 if a>b else .5 if a==b else 0 for a in p for b in n)/(len(p)*len(n))
def evaluate(model,pairs):
 truth=[];scores=[];false=[];detected=[];leads=[]
 for roles in pairs.values():
  diff=divergence(roles["control"],roles["treatment"]);cs=model.score_trajectory(roles["control"]);ts=model.score_trajectory(roles["treatment"]);false.append(any(x>model.threshold for x in cs));alarms=[i for i,x in enumerate(ts,1) if x>model.threshold];detected.append(bool(diff and any(i in diff for i in alarms)))
  if diff and alarms:leads.append(min(diff)-min(alarms))
  for role,traj,values in (("control",roles["control"],cs),("treatment",roles["treatment"],ts)):
   for event,score in zip(traj["steps"],values):truth.append(role=="treatment" and event["step"] in diff);scores.append(score)
 return {"auroc":round(auroc(truth,scores),4),"false_alarm":round(mean(false),4),"pair_detection":round(mean(detected),4),"alarm_lead":round(mean(leads),3) if leads else "NA"}
def main():
 p=argparse.ArgumentParser();base=ROOT/"results/environment_influence_expansion";p.add_argument("--raw-dir",type=Path,default=base/"raw");p.add_argument("--output-dir",type=Path,default=base/"contextual_ndtr");a=p.parse_args();pairs=defaultdict(dict)
 for path in a.raw_dir.glob("*.json"):pair,role=parse(path);pairs[pair][role]=json.loads(path.read_text())
 dev={k:v for k,v in pairs.items() if not k.endswith("_s02")};holdout={k:v for k,v in pairs.items() if k.endswith("_s02")};controls=[x["control"] for x in dev.values()];rows=[]
 for name,model in (("NDTR",NormalDelegationTransitionRetrieval(128,5,15)),("C-NDTR",ContextualNDTR(128,5,15,3))):
  model.fit(controls,contrastive=False);model.threshold=percentile([max(model.score_trajectory(x)) for x in controls],.95);rows.append({"method":name,"threshold":round(model.threshold,6),**{f"dev_{k}":v for k,v in evaluate(model,dev).items()},**{f"holdout_{k}":v for k,v in evaluate(model,holdout).items()}})
 a.output_dir.mkdir(parents=True,exist_ok=True)
 with (a.output_dir/"contextual_ndtr_comparison.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 report={"conditioning":["task_family","observable_absolute_phase","previous_tool_state"],"backoff":"task+phase+tool -> task+phase -> task memory","training":"seed 0/1 controls only","evaluation":"seed 2 paired holdout","manual_labels_used":False,"results":rows};(a.output_dir/"contextual_ndtr_summary.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report,indent=2))
if __name__=="__main__":main()
