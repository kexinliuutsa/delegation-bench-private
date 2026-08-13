#!/usr/bin/env python3
"""Frozen-result uncertainty report for Experiment 66 (not a new experiment)."""
from __future__ import annotations
import argparse,csv,json,math,random
from pathlib import Path
from statistics import mean
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.cross_domain_monitor_transfer import auroc,load,percentile
from experiments.paradigm_invariant_delegation_representation import decorate,ordered
from experiments.pidr_downstream_monitor import TransitionKNN,changed
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation

def percentile_value(values,q):
 values=sorted(values);index=(len(values)-1)*q;lower=math.floor(index);upper=math.ceil(index)
 return values[lower] if lower==upper else values[lower]*(upper-index)+values[upper]*(index-lower)
def wilson(successes,total,z=1.959963984540054):
 p=successes/total;denominator=1+z*z/total;center=(p+z*z/(2*total))/denominator;radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator;return max(0,center-radius),min(1,center+radius)
def collect(model,train,web):
 threshold=percentile([max(model.score(x,exclude=i)) for i,x in enumerate(train)],.95);rows={}
 for pair,roles in sorted(web.items()):
  diff=changed(roles['control'],roles['treatment']);cs=model.score(roles['control']);ts=model.score(roles['treatment']);labels=[];scores=[]
  for role,trajectory,values in (('control',roles['control'],cs),('treatment',roles['treatment'],ts)):
   for event,score in zip(trajectory['steps'],values):labels.append(role=='treatment' and event['step'] in diff);scores.append(score)
  rows[pair]={'labels':labels,'scores':scores,'false_alarm':any(x>threshold for x in cs),'detected':any(i in diff and x>threshold for i,x in enumerate(ts,1))}
 return rows
def summarize(name,rows,resamples,subset):
 keys=sorted(rows);labels=[x for key in keys for x in rows[key]['labels']];scores=[x for key in keys for x in rows[key]['scores']];point_auc=auroc(labels,scores);false=sum(rows[key]['false_alarm'] for key in keys);detected=sum(rows[key]['detected'] for key in keys);rng=random.Random(66001);aucs=[];fas=[];detections=[]
 for _ in range(resamples):
  sample=[rng.choice(keys) for _ in keys];y=[x for key in sample for x in rows[key]['labels']];s=[x for key in sample for x in rows[key]['scores']];area=auroc(y,s)
  if area is not None:aucs.append(area)
  fas.append(mean(rows[key]['false_alarm'] for key in sample));detections.append(mean(rows[key]['detected'] for key in sample))
 fa_low,fa_high=wilson(false,len(keys));det_low,det_high=wilson(detected,len(keys))
 return {'eval_subset':subset,'representation':name,'pairs':len(keys),'step_auroc':round(point_auc,4),'step_auroc_cluster_bootstrap_low':round(percentile_value(aucs,.025),4),'step_auroc_cluster_bootstrap_high':round(percentile_value(aucs,.975),4),'false_alarm_count':false,'false_alarm_rate':round(false/len(keys),4),'false_alarm_wilson_low':round(fa_low,4),'false_alarm_wilson_high':round(fa_high,4),'pair_detection_count':detected,'pair_detection_rate':round(detected/len(keys),4),'pair_detection_wilson_low':round(det_low,4),'pair_detection_wilson_high':round(det_high,4),'resamples':resamples}
def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--pidr-model',type=Path,default=base/'pidr/pidr_model.json');p.add_argument('--output-dir',type=Path,default=base/'pidr_statistical_report');p.add_argument('--resamples',type=int,default=10000);a=p.parse_args();cohorts=load(a.rollouts);decorate(cohorts);coding=cohorts['gpt5_minimal_coding_agent'];web=cohorts['gpt5_minimal_web_agent'];train=ordered(coding,0)+ordered(coding,1);pidr=ParadigmInvariantDelegationRepresentation.load(a.pidr_model);results=[]
 subsets={'seed2_fully_held_out':{pair:roles for pair,roles in web.items() if roles['control']['seed']==2},'seed01_seen_by_pidr':{pair:roles for pair,roles in web.items() if roles['control']['seed'] in {0,1}},'all_mixed_diagnostic':web}
 for name,encoder in (('raw_transition_kNN',None),('PIDR_transition_kNN',pidr)):
  model=TransitionKNN(encoder,5).fit(train)
  for subset,pairs in subsets.items():results.append(summarize(name,collect(model,train,pairs),a.resamples,subset))
 a.output_dir.mkdir(parents=True,exist_ok=True)
 heldout=[row for row in results if row['eval_subset']=='seed2_fully_held_out']
 with (a.output_dir/'experiment66_seed2_confidence_intervals.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(heldout[0]));w.writeheader();w.writerows(heldout)
 with (a.output_dir/'experiment66_seen_unseen_breakdown.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 # Backward-compatible filename now contains the explicit subset column; this
 # prevents the former mixed 48-pair table from being mistaken for held-out.
 with (a.output_dir/'experiment66_confidence_intervals.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 report={'analysis':'Experiment 66 seed-2 held-out uncertainty with seen/unseen diagnostic','new_experiment':False,'primary_eval_subset':'seed2_fully_held_out','primary_pairs':16,'representation_training_disclosure':'PIDR used Coding and Web seed 0/1 alignment/separation pairs; seed 2 was not used to train PIDR.','mixed_48_pair_result_is_primary':False,'bootstrap_unit':'control/treatment trajectory pair','bootstrap_seed':66001,'rate_interval':'Wilson score 95%','auroc_interval':'pair-cluster percentile bootstrap 95%','primary_results':heldout,'diagnostic_results':results};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
