#!/usr/bin/env python3
"""Experiment 68: deterministic pair-cluster bootstrap for pair-level AUROC."""
from __future__ import annotations
import argparse,csv,json,math,random
from pathlib import Path
from statistics import mean,pstdev

ROOT=Path(__file__).resolve().parents[1]
def auc(labels,scores):
 pos=[s for y,s in zip(labels,scores) if y];neg=[s for y,s in zip(labels,scores) if not y]
 return sum((p>n)+.5*(p==n) for p in pos for n in neg)/(len(pos)*len(neg))
def quantile(values,q):
 values=sorted(values);i=(len(values)-1)*q;lo=math.floor(i);hi=math.ceil(i)
 return values[lo] if lo==hi else values[lo]*(hi-i)+values[hi]*(i-lo)
def pair_auc(rows):
 c=[mean(x['control_scores']) for x in rows];t=[mean(x['treatment_scores']) for x in rows];return auc([False]*len(rows)+[True]*len(rows),c+t)
def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation/pibr_oof_threshold_diagnostics';p.add_argument('--scores',type=Path,default=base/'oof_trajectory_scores.jsonl');p.add_argument('--output-dir',type=Path,default=ROOT/'results/protocol_validity');p.add_argument('--resamples',type=int,default=10000);p.add_argument('--seed',type=int,default=68001);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
 groups={}
 for line in a.scores.read_text().splitlines():
  row=json.loads(line);groups.setdefault(row['representation'],[]).append(row)
 csvrows=[];distributions={};delta_summaries=[]
 for representation,rows in sorted(groups.items()):
  equal=[x for x in rows if len(x['control_scores'])==len(x['treatment_scores'])];rng=random.Random(a.seed);full_dist=[];equal_dist=[];delta_dist=[]
  for _ in range(a.resamples):
   sampled=[rng.choice(rows) for _ in rows];sampled_equal=[x for x in sampled if len(x['control_scores'])==len(x['treatment_scores'])]
   # A vanishing equal subset is practically impossible here (32/48 equal), but
   # skip defensively rather than bootstrap individual steps.
   if not sampled_equal:continue
   fa=pair_auc(sampled);ea=pair_auc(sampled_equal);full_dist.append(fa);equal_dist.append(ea);delta_dist.append(fa-ea)
  for subset,data,dist in [('web_full_48',rows,full_dist),('web_equal_length_32',equal,equal_dist)]:
   point=pair_auc(data);csvrows.append({'representation':representation,'method':'trajectory_mean_5NN_transition_score','dataset_subset':subset,'pairs':len(data),'auroc':round(point,4),'bootstrap_ci_low':round(quantile(dist,.025),4),'bootstrap_ci_high':round(quantile(dist,.975),4),'bootstrap_standard_error':round(pstdev(dist),4),'bootstrap_unit':'pair','replicates':len(dist),'bootstrap_seed':a.seed})
  delta=pair_auc(rows)-pair_auc(equal);delta_summaries.append({'representation':representation,'delta_definition':'AUROC_full_minus_AUROC_equal_length','delta_point_estimate':round(delta,4),'bootstrap_ci_low':round(quantile(delta_dist,.025),4),'bootstrap_ci_high':round(quantile(delta_dist,.975),4),'probability_delta_gt_0':round(sum(x>0 for x in delta_dist)/len(delta_dist),4),'replicates':len(delta_dist)})
  distributions[representation]={'full_auroc':full_dist,'equal_length_auroc':equal_dist,'delta_full_minus_equal':delta_dist}
 with (a.output_dir/'pair_bootstrap_ci.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
 (a.output_dir/'pair_bootstrap_distributions.json').write_text(json.dumps({'resampling_unit':'pair','seed':a.seed,'replicates':a.resamples,'coding_status':'NOT_AVAILABLE: no comparable coding OOF trajectory-score file exists','distributions':distributions})+'\n')
 summary={'resampling_unit':'pair','individual_steps_bootstrapped':False,'replicates':a.resamples,'seed':a.seed,'results':csvrows,'delta_auroc':delta_summaries,'coding_evaluation':'NOT_AVAILABLE: the same OOF pair-level score was not persisted for Coding; no value was invented or hard-coded.'};(a.output_dir/'pair_bootstrap_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
