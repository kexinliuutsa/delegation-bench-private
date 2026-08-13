#!/usr/bin/env python3
"""Train LDTD on controls and evaluate paired intervention divergence."""
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
def percentile(values,q):values=sorted(values);return values[max(0,min(len(values)-1,math.ceil(q*len(values))-1))]
def divergence(control,treatment):return {x["treatment_step"] for x in align(control["steps"],treatment["steps"]) if x.get("treatment_step") and x["relation"] in {"NEW","MODIFIED"}}
def auc(truth,scores):
 p=[s for y,s in zip(truth,scores) if y];n=[s for y,s in zip(truth,scores) if not y];return sum(1 if a>b else .5 if a==b else 0 for a in p for b in n)/(len(p)*len(n))
def main():
 p=argparse.ArgumentParser();base=ROOT/"results/environment_influence_expansion";p.add_argument("--raw-dir",type=Path,default=base/"raw");p.add_argument("--output-dir",type=Path,default=base/"latent_delegation_transition");a=p.parse_args();pairs=defaultdict(dict)
 for path in a.raw_dir.glob("*.json"):pair,role=parse(path);pairs[pair][role]=json.loads(path.read_text())
 if len(pairs)!=48 or any(set(x)!={"control","treatment"} for x in pairs.values()):raise SystemExit("requires 48 complete pairs")
 controls=[x["control"] for x in pairs.values()];model=LatentDelegationTransitionDetector(128).fit(controls);model.threshold=percentile([max(model.score_trajectory(x)) for x in controls],.95);truth=[];scores=[];control_alarm=[];pair_detection=[];leads=[];step_rows=[]
 for pair,roles in sorted(pairs.items()):
  changed=divergence(roles["control"],roles["treatment"]);role_scores={role:model.score_trajectory(value) for role,value in roles.items()};control_alarm.append(any(x>model.threshold for x in role_scores["control"]));alarms=[i for i,x in enumerate(role_scores["treatment"],1) if x>model.threshold];pair_detection.append(bool(changed and any(x in changed for x in alarms)))
  if changed and alarms:leads.append(min(changed)-min(alarms))
  for role,trajectory in roles.items():
   for event,score in zip(trajectory["steps"],role_scores[role]):target=role=="treatment" and event["step"] in changed;truth.append(target);scores.append(score);step_rows.append({"pair_id":pair,"trajectory_role":role,"step":event["step"],"latent_transition_surprise":round(score,6),"alarm":score>model.threshold,"counterfactual_divergence_proxy":target})
 predicted=[x>model.threshold for x in scores];tp=sum(y and z for y,z in zip(truth,predicted));fp=sum(not y and z for y,z in zip(truth,predicted));fn=sum(y and not z for y,z in zip(truth,predicted));precision=tp/(tp+fp) if tp+fp else 0;recall=tp/(tp+fn) if tp+fn else 0;metrics={"divergence_detection_auroc":round(auc(truth,scores),4),"precision":round(precision,4),"recall":round(recall,4),"f1":round(2*precision*recall/(precision+recall),4) if precision+recall else 0,"treatment_pair_detection":round(mean(pair_detection),4),"control_false_alarm":round(mean(control_alarm),4),"mean_alarm_lead_to_first_divergence":round(mean(leads),3) if leads else "NA","threshold":round(model.threshold,6)}
 a.output_dir.mkdir(parents=True,exist_ok=True);model.save(a.output_dir/"latent_delegation_transition_detector.json")
 with (a.output_dir/"latent_transition_scores.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(step_rows[0]));w.writeheader();w.writerows(step_rows)
 report={"training":"48 control trajectories only","encoder_inputs":["task","previous_actions","current_observation","current_action"],"contrastive_positive":"same task family and authority-stage proxy across seeds","contrastive_negative":"different action-derived stage proxies","manual_stage_used_at_inference":False,"unsafe_attack_source_labels_used":False,"paired_ground_truth":"control-treatment action divergence proxy","metrics":metrics};(a.output_dir/"latent_transition_summary.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report,indent=2))
if __name__=="__main__":main()
