#!/usr/bin/env python3
"""Experiment 62: Web→Coding transfer and the bidirectional matrix.

No detector is changed. We report both the full target domain and the subset
for which the monitor's pre-existing task-family router has training support.
"""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.cross_domain_monitor_transfer import evaluate,load,percentile
from models.authority_transition_detector import task_family
from models.counterfactual_delegation_monitor import CounterfactualDelegationMonitor
from models.latent_delegation_transition import NormalDelegationTransitionRetrieval

def fitted_methods(controls):
 ndtr=NormalDelegationTransitionRetrieval(128,5,15);ndtr.fit(controls,contrastive=False);ndtr_threshold=percentile([max(ndtr.score_trajectory(x)) for x in controls],.95)
 calibration=[]
 for index,trajectory in enumerate(controls):
  model=CounterfactualDelegationMonitor([x for other,x in enumerate(controls) if other!=index])
  try:calibration.append(max(model.score_trajectory(trajectory)))
  except (ValueError,KeyError):pass
 cdm=CounterfactualDelegationMonitor(controls);cdm_threshold=percentile(calibration,.95)
 return [('NDTR',ndtr,ndtr_threshold),('CDM',cdm,cdm_threshold)]

def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--within-summary',type=Path,default=base/'monitor_evaluation/summary.json');p.add_argument('--forward-summary',type=Path,default=base/'cross_domain_transfer/summary.json');p.add_argument('--output-dir',type=Path,default=base/'bidirectional_transfer');a=p.parse_args();cohorts=load(a.rollouts);web=cohorts['gpt5_minimal_web_agent'];coding=cohorts['gpt5_minimal_coding_agent'];web_train=[v['control'] for v in web.values() if v['control']['seed'] in {0,1}];supported={task_family(x['task']) for x in web_train};common={pair:roles for pair,roles in coding.items() if task_family(roles['control']['task']) in supported};reverse=[]
 for name,model,threshold in fitted_methods(web_train):
  full=evaluate(model,coding,threshold);covered_auroc=full['auroc'];full['auroc']='NA' if full['coverage']<1 else full['auroc']
  reverse.append({'method':name,'direction':'web_to_coding','evaluation_scope':'full_target','training_controls':len(web_train),'test_pairs':len(coding),'task_family_support':','.join(sorted(supported)),'covered_subset_auroc':covered_auroc,**full})
  reverse.append({'method':name,'direction':'web_to_coding','evaluation_scope':'common_support','training_controls':len(web_train),'test_pairs':len(common),'task_family_support':','.join(sorted(supported)),'covered_subset_auroc':'NA',**evaluate(model,common,threshold)})
 within=json.loads(a.within_summary.read_text())['results'];forward=json.loads(a.forward_summary.read_text())['results'];matrix=[]
 for row in within:
  if row['method'] not in {'NDTR','CDM'}:continue
  domain='coding' if 'coding' in row['agent_id'] else 'web';matrix.append({'method':row['method'],'direction':f'{domain}_to_{domain}','evaluation_scope':'seed2_holdout','auroc':row['auroc'],'control_false_alarm':row['control_false_alarm'],'pair_detection':row['pair_detection'],'coverage':1.0})
 for row in forward:matrix.append({'method':row['method'],'direction':'coding_to_web','evaluation_scope':'full_target','auroc':row['auroc'],'control_false_alarm':row['control_false_alarm'],'pair_detection':row['pair_detection'],'coverage':row['coverage']})
 for row in reverse:matrix.append({'method':row['method'],'direction':row['direction'],'evaluation_scope':row['evaluation_scope'],'auroc':row['auroc'],'control_false_alarm':row['control_false_alarm'],'pair_detection':row['pair_detection'],'coverage':row['coverage']})
 a.output_dir.mkdir(parents=True,exist_ok=True)
 with (a.output_dir/'web_to_coding.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(reverse[0]));w.writeheader();w.writerows(reverse)
 with (a.output_dir/'bidirectional_transfer_matrix.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
 report={'experiment':62,'status':'complete_and_frozen','new_models_trained':False,'web_training':'seed 0/1 control trajectories only','coding_testing':'all 48 pairs plus common task-router support subset','router_confound':'The unchanged task_family function maps all Web tasks to bug_fix, so full reverse-transfer coverage must be separated from common-support performance. Full-target AUROC is NA when coverage is incomplete.','reverse_results':reverse,'matrix':matrix};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
