#!/usr/bin/env python3
"""Experiment 2: contrastive projection ablation for LDTD."""
from __future__ import annotations
import argparse,csv,json,math,re,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.authority_source_alignment import align
from models.latent_delegation_transition import LatentDelegationTransitionDetector
def parse(path):return re.match(r"(.+)_(control|treatment)\.json$",path.name).groups()
def load_pairs(raw):
 pairs=defaultdict(dict)
 for path in raw.glob("*.json"):pair,role=parse(path);pairs[pair][role]=json.loads(path.read_text())
 return pairs
def percentile(values,q):values=sorted(values);return values[max(0,min(len(values)-1,math.ceil(q*len(values))-1))]
def changed(control,treatment):return {x["treatment_step"] for x in align(control["steps"],treatment["steps"]) if x.get("treatment_step") and x["relation"] in {"NEW","MODIFIED"}}
def auc(truth,scores):
 p=[s for y,s in zip(truth,scores) if y];n=[s for y,s in zip(truth,scores) if not y];return sum(1 if a>b else .5 if a==b else 0 for a in p for b in n)/(len(p)*len(n))
def evaluate(pairs,contrastive=True,history_window=4):
 controls=[x["control"] for x in pairs.values()];model=LatentDelegationTransitionDetector(128,history_window).fit(controls,contrastive=contrastive);model.threshold=percentile([max(model.score_trajectory(x)) for x in controls],.95);truth=[];scores=[];false=[];detected=[];leads=[]
 for roles in pairs.values():
  divergence=changed(roles["control"],roles["treatment"]);control_scores=model.score_trajectory(roles["control"]);treatment_scores=model.score_trajectory(roles["treatment"]);false.append(any(x>model.threshold for x in control_scores));alarms=[i for i,x in enumerate(treatment_scores,1) if x>model.threshold];detected.append(bool(divergence and any(i in divergence for i in alarms)))
  if divergence and alarms:leads.append(min(divergence)-min(alarms))
  for role,trajectory,values in (("control",roles["control"],control_scores),("treatment",roles["treatment"],treatment_scores)):
   for event,score in zip(trajectory["steps"],values):truth.append(role=="treatment" and event["step"] in divergence);scores.append(score)
 return model,{"auroc":round(auc(truth,scores),4),"control_false_alarm":round(mean(false),4),"treatment_pair_detection":round(mean(detected),4),"mean_alarm_lead":round(mean(leads),3) if leads else "NA","threshold":round(model.threshold,6)}
def main():
 p=argparse.ArgumentParser();base=ROOT/"results/environment_influence_expansion";p.add_argument("--raw-dir",type=Path,default=base/"raw");p.add_argument("--output-dir",type=Path,default=base/"ldtd_ablation");a=p.parse_args();pairs=load_pairs(a.raw_dir);rows=[]
 for enabled in (False,True):_,result=evaluate(pairs,contrastive=enabled);rows.append({"model":"random_hashed_encoder" if not enabled else "contrastive_latent_encoder","contrastive_learning":enabled,**result})
 a.output_dir.mkdir(parents=True,exist_ok=True)
 with (a.output_dir/"contrastive_ablation.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (a.output_dir/"contrastive_ablation.json").write_text(json.dumps({"unsafe_labels_used":False,"paired_labels_used_for_training":False,"results":rows},indent=2)+"\n");print(json.dumps(rows,indent=2))
if __name__=="__main__":main()

