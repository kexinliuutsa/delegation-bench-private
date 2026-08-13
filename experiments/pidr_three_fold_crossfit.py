#!/usr/bin/env python3
"""Three-fold leave-one-seed-out cross-fitting for the frozen PIDR/PIBR POC."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.cross_domain_monitor_transfer import load
from experiments.paradigm_invariant_delegation_representation import decorate,intervention_pairs,ordered,progress_pairs
from experiments.pidr_downstream_monitor import TransitionKNN
from experiments.pidr_statistical_report import collect,summarize
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation

def write_csv(path,rows):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--output-dir',type=Path,default=base/'pidr_three_fold_crossfit');p.add_argument('--resamples',type=int,default=10000);a=p.parse_args();cohorts=load(a.rollouts);decorate(cohorts);coding=cohorts['gpt5_minimal_coding_agent'];web=cohorts['gpt5_minimal_web_agent'];a.output_dir.mkdir(parents=True,exist_ok=True);fold_rows=[];pooled={'raw_transition_kNN':{},'PIBR_transition_kNN':{}};audit=[]
 for heldout_seed in (0,1,2):
  train_seeds={0,1,2}-{heldout_seed};positives=[]
  for seed in sorted(train_seeds):positives+=progress_pairs(ordered(coding,seed),ordered(web,seed))
  negatives=intervention_pairs(coding,train_seeds)+intervention_pairs(web,train_seeds);encoder=ParadigmInvariantDelegationRepresentation();encoder.fit(positives,negatives);encoder.save(a.output_dir/f'pibr_fold{heldout_seed}_model.json');train=[trajectory for seed in sorted(train_seeds) for trajectory in ordered(coding,seed)];evaluation={pair:roles for pair,roles in web.items() if roles['control']['seed']==heldout_seed}
  for name,representation in (('raw_transition_kNN',None),('PIBR_transition_kNN',encoder)):
   model=TransitionKNN(representation,5).fit(train);rows=collect(model,train,evaluation);summary=summarize(name,rows,a.resamples,f'heldout_seed_{heldout_seed}');fold_rows.append({'fold':heldout_seed,'heldout_seed':heldout_seed,'training_seeds':'|'.join(map(str,sorted(train_seeds))),'alignment_examples':len(positives),'separation_examples':len(negatives),**summary});pooled[name].update(rows)
   for pair,row in sorted(rows.items()):audit.append({'fold':heldout_seed,'heldout_seed':heldout_seed,'representation':name,'pair_id':pair,'false_alarm':row['false_alarm'],'pair_detected':row['detected'],'step_labels':row['labels'],'step_scores':row['scores']})
 pooled_rows=[summarize(name,rows,a.resamples,'pooled_out_of_fold') for name,rows in pooled.items()]
 if any(row['pairs']!=16 for row in fold_rows) or any(row['pairs']!=48 for row in pooled_rows):raise SystemExit('cross-fitting coverage failure')
 write_csv(a.output_dir/'per_fold_metrics.csv',fold_rows);write_csv(a.output_dir/'pooled_oof_metrics.csv',pooled_rows);(a.output_dir/'oof_pair_scores.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in audit));report={'analysis':'three-fold leave-one-seed-out cross-fitting','paper_facing_name':'PIBR: Paradigm-Invariant Behavioral Representation','legacy_implementation_name':'PIDR','folds':3,'representation_retrained_per_fold':True,'normal_memory_rebuilt_per_fold':True,'threshold_recalibrated_per_fold':True,'each_pair_evaluated_once':True,'unsafe_authority_or_divergence_labels_used_by_detector':False,'per_fold':fold_rows,'pooled_out_of_fold':pooled_rows};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
