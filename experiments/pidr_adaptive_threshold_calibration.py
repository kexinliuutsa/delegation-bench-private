#!/usr/bin/env python3
"""Experiment 67: zero-shot vs five-shot benign threshold calibration."""
from __future__ import annotations
import argparse,csv,json,random
from pathlib import Path
from statistics import mean,median
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.cross_domain_monitor_transfer import load,percentile
from experiments.paradigm_invariant_delegation_representation import decorate,ordered
from experiments.pidr_downstream_monitor import TransitionKNN,changed
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation

def quantile(values,q):
 values=sorted(values);return values[max(0,min(len(values)-1,round(q*(len(values)-1))))]
def pair_scores(model,web):
 output={}
 for pair,roles in sorted(web.items()):output[pair]={'control':model.score(roles['control']),'treatment':model.score(roles['treatment']),'changed':changed(roles['control'],roles['treatment'])}
 return output
def evaluate(values,threshold,pairs):
 false=[];detected=[]
 for pair in pairs:
  row=values[pair];false.append(any(x>threshold for x in row['control']));detected.append(any(i in row['changed'] and x>threshold for i,x in enumerate(row['treatment'],1)))
 return sum(false)/len(false),sum(detected)/len(detected)
def summarize(name,model,train,web,trials,shots):
 calibration=[max(model.score(trajectory,exclude=i)) for i,trajectory in enumerate(train)];zero_threshold=percentile(calibration,.95);values=pair_scores(model,web);all_pairs=sorted(values);zero_fa,zero_detection=evaluate(values,zero_threshold,all_pairs);rng=random.Random(6701);trial_rows=[]
 for trial in range(trials):
  selected=sorted(rng.sample(all_pairs,shots));evaluation=[pair for pair in all_pairs if pair not in selected]
  # With five samples, the conformal 80%-coverage threshold is the maximum
  # benign trajectory score: ceil((n+1)*(1-.2)) = 5th order statistic.
  threshold=max(max(values[pair]['control']) for pair in selected);fa,detection=evaluate(values,threshold,evaluation);trial_rows.append({'representation':name,'trial':trial,'calibration_pairs':'|'.join(selected),'evaluation_pairs':len(evaluation),'threshold':threshold,'false_alarm':fa,'pair_detection':detection})
 fas=[x['false_alarm'] for x in trial_rows];detections=[x['pair_detection'] for x in trial_rows];thresholds=[x['threshold'] for x in trial_rows]
 summary={'representation':name,'zero_shot_threshold':round(zero_threshold,6),'zero_shot_pairs':len(all_pairs),'zero_shot_false_alarm':round(zero_fa,4),'zero_shot_pair_detection':round(zero_detection,4),'calibration_shots':shots,'trials':trials,'evaluation_pairs_per_trial':len(all_pairs)-shots,'five_shot_threshold_mean':round(mean(thresholds),6),'five_shot_false_alarm_mean':round(mean(fas),4),'five_shot_false_alarm_median':round(median(fas),4),'five_shot_false_alarm_p05':round(quantile(fas,.05),4),'five_shot_false_alarm_p95':round(quantile(fas,.95),4),'five_shot_pair_detection_mean':round(mean(detections),4),'five_shot_pair_detection_median':round(median(detections),4),'five_shot_pair_detection_p05':round(quantile(detections,.05),4),'five_shot_pair_detection_p95':round(quantile(detections,.95),4)}
 return summary,trial_rows
def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--pidr-model',type=Path,default=base/'pidr/pidr_model.json');p.add_argument('--output-dir',type=Path,default=base/'pidr_adaptive_calibration');p.add_argument('--trials',type=int,default=200);p.add_argument('--shots',type=int,default=5);a=p.parse_args()
 if a.shots!=5:raise SystemExit('Experiment 67 is frozen at five calibration trajectories')
 cohorts=load(a.rollouts);decorate(cohorts);coding=cohorts['gpt5_minimal_coding_agent'];web=cohorts['gpt5_minimal_web_agent'];train=ordered(coding,0)+ordered(coding,1);pidr=ParadigmInvariantDelegationRepresentation.load(a.pidr_model);summaries=[];trial_rows=[]
 for name,encoder in (('raw',None),('PIDR',pidr)):
  model=TransitionKNN(encoder,5).fit(train);summary,rows=summarize(name,model,train,web,a.trials,a.shots);summaries.append(summary);trial_rows.extend(rows)
 by_representation={name:{row['trial']:row for row in trial_rows if row['representation']==name} for name in ('raw','PIDR')};paired=[(by_representation['raw'][trial],by_representation['PIDR'][trial]) for trial in range(a.trials)];comparison={'mean_false_alarm_delta_pidr_minus_raw':round(mean(pidr_row['false_alarm']-raw_row['false_alarm'] for raw_row,pidr_row in paired),4),'mean_pair_detection_delta_pidr_minus_raw':round(mean(pidr_row['pair_detection']-raw_row['pair_detection'] for raw_row,pidr_row in paired),4),'pidr_false_alarm_no_worse_trial_rate':round(mean(pidr_row['false_alarm']<=raw_row['false_alarm'] for raw_row,pidr_row in paired),4),'pidr_detection_no_worse_trial_rate':round(mean(pidr_row['pair_detection']>=raw_row['pair_detection'] for raw_row,pidr_row in paired),4),'pidr_jointly_no_worse_trial_rate':round(mean(pidr_row['false_alarm']<=raw_row['false_alarm'] and pidr_row['pair_detection']>=raw_row['pair_detection'] for raw_row,pidr_row in paired),4)}
 a.output_dir.mkdir(parents=True,exist_ok=True)
 with (a.output_dir/'adaptive_calibration_summary.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
 with (a.output_dir/'adaptive_calibration_trials.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(trial_rows[0]));w.writeheader();w.writerows(trial_rows)
 report={'experiment':67,'model_retrained':False,'detector_changed':False,'calibration':'five benign Web control trajectories; conformal 80%-coverage maximum score','calibration_pairs_excluded_from_evaluation':True,'trial_sampling_seed':6701,'test_labels_used_for_threshold':False,'results':summaries,'paired_split_comparison':comparison};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
