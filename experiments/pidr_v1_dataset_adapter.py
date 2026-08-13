#!/usr/bin/env python3
"""Read-only split adapter from Benchmark v1 trajectories to PIDR consumers."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from delegation_bench_v1_common import BENCH,RESULTS
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=RESULTS/'normalized/trajectories.jsonl');p.add_argument('--output',type=Path,default=RESULTS/'manifests/pidr_v1_dataset_view.json');a=p.parse_args();split=json.loads((BENCH/'split.json').read_text());pairs={}
 if a.input.exists():
  for line in a.input.read_text().splitlines():
   row=json.loads(line);pairs.setdefault(row['pair_id'],{})[row['condition']]=row
 train=[];interventions=[];sealed=[]
 for pid,roles in pairs.items():
  if set(roles)!={'control','treatment'}:continue
  sample={'pair_id':pid,'paradigm':roles['control']['paradigm'],'seed':roles['control']['seed'],'control_trajectory_id':roles['control']['trajectory_id'],'treatment_trajectory_id':roles['treatment']['trajectory_id']}
  if sample['paradigm'] in {'coding','web'} and sample['seed'] in split['train']['seeds']:train.append({'trajectory_id':roles['control']['trajectory_id'],'paradigm':sample['paradigm'],'role':'benign_control'});interventions.append(sample)
  elif sample['paradigm'] in {'coding','web'} and sample['seed'] in split['in_domain_sealed_test']['seeds']:sealed.append(sample)
 report={'benchmark_version':'v1','pidr_retrained':False,'training_split':'coding+web seeds 0,1,2','development_split':'coding+web seed 3','sealed_in_domain_test_split':'coding+web seed 4','future_out_of_domain_test':'UNASSIGNED / DATA_NOT_COLLECTED','benign_cross_paradigm_training_samples':train,'intervention_control_treatment_pairs':interventions,'sealed_in_domain_test_samples':sealed,'future_third_paradigm_test_samples':[],'test_outcomes_exposed_to_training':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:len(report[k]) for k in ('benign_cross_paradigm_training_samples','intervention_control_treatment_pairs','sealed_in_domain_test_samples')},indent=2))
if __name__=='__main__':main()
