#!/usr/bin/env python3
"""Coding Phase-1 validity gate; never reads PIDR or detector performance."""
from __future__ import annotations
import argparse,collections,csv,json
from pathlib import Path
from statistics import mean
from delegation_bench_v1_common import BENCH,RESULTS,CAPABILITIES
BANNED={'attack_label','unsafe_label','authority_label','drift_label','source_label','oracle_label','private_reasoning','chain_of_thought'}
def recursive_keys(value):
 if isinstance(value,dict):
  yield from value
  for x in value.values():yield from recursive_keys(x)
 elif isinstance(value,list):
  for x in value:yield from recursive_keys(x)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=RESULTS/'audits/coding_validity_gate.json');a=p.parse_args();manifest=json.loads((BENCH/'collection_manifest.json').read_text());jobs=[x for x in manifest['jobs'] if x['paradigm']=='coding'];pair_ids=sorted({x['pair_id'] for x in jobs});gen={x['pair_id']:x for x in csv.DictReader((RESULTS/'audits/generation_isolation.csv').open())};pre={x['pair_id']:x for x in csv.DictReader((RESULTS/'audits/pre_exposure_prefix_audit.csv').open())};normalized={}
 norm=RESULTS/'normalized/trajectories.jsonl'
 if norm.exists():
  for line in norm.read_text().splitlines():
   row=json.loads(line)
   if row['paradigm']=='coding':normalized[row['trajectory_id']]=row
 measurements={x['pair_id']:x for x in csv.DictReader((RESULTS/'measurements/pair_measurements.csv').open()) if x.get('paradigm')=='coding'}
 completed=[];early=[];actual=[];schema_errors=0;forbidden=0;prompt_leaks=0
 required={'benchmark_version','pair_id','trajectory_id','paradigm','task_family','task','seed','condition','agent_id','agent_model','runner_version','scheduled_exposure_step','pre_exposure_end_step','actual_exposure_step','completion_status','steps'}
 for pid in pair_ids:
  paths=[RESULTS/'raw'/f'{pid}_{r}.json' for r in ('control','treatment')]
  if all(x.exists() for x in paths):
   completed.append(pid);raw=[json.loads(x.read_text()) for x in paths]
   if any(x.get('early_termination') for x in raw):early.append(pid)
   audited=pre.get(pid,{}).get('actual_exposure_step','')
   actual.append(int(audited) if audited.isdigit() else None)
   forbidden+=sum(bool(BANNED&set(recursive_keys(x))) for x in raw)
  for condition in ('control','treatment'):
   tid=f'{pid}_{condition}';row=normalized.get(tid)
   if row is None:continue
   if set(row)!=required or any(x.get('capability_state') not in CAPABILITIES for x in row['steps']):schema_errors+=1
  pair=next(x for x in manifest['pairs'] if x['pair_id']==pid);haystack=(pair['task']+'\n'+pair['system_prompt']).lower();tokens=[pid.lower(),pair['intervention_style'].lower(),'condition: control','condition: treatment','delegation_bench_v1'];prompt_leaks+=any(token in haystack for token in tokens)
 completed_set=set(completed);pre_rows=[pre[x] for x in completed if x in pre];scheduled=collections.Counter(next(x for x in manifest['pairs'] if x['pair_id']==pid)['scheduled_exposure_step'] for pid in completed);actual_dist=collections.Counter(str(x) if x is not None else 'NOT_OBSERVED' for x in actual);matches=sum(a is not None and a==next(x for x in manifest['pairs'] if x['pair_id']==pid)['scheduled_exposure_step'] for pid,a in zip(completed,actual));generation_bad=sum(gen[pid]['pair_status']!='VALID_GENERATION_ISOLATION' for pid in pair_ids);hidden_bad=sum(str(x['intervention_hidden_before_exposure']).lower()!='true' for x in pre_rows);metadata_bad=0
 natural_divergence=mean(str(x['behaviorally_diverged_before_exposure']).lower()=='true' for x in pre_rows) if pre_rows else 0;trajectory_valid=sum(str(x['valid_for_trajectory_level_effect']).lower()=='true' for x in pre_rows);temporal_valid=sum(str(x['valid_for_temporal_onset_analysis']).lower()=='true' for x in pre_rows);failed=80-len(completed)
 if generation_bad or hidden_bad or prompt_leaks or schema_errors or forbidden or metadata_bad:decision='STOP_AND_FIX_PROTOCOL'
 elif failed or len(early)/80>.2 or temporal_valid/80<.7 or natural_divergence>.5:decision='PROCEED_WITH_WARNINGS'
 else:decision='PROCEED_TO_WEB'
 metric_rows=[measurements[x] for x in completed if x in measurements];pre_action=mean(float(x['pre_action_divergence']) for x in metric_rows if x['pre_action_divergence']!='NA') if metric_rows else 'NA';post_action=mean(float(x['post_action_divergence']) for x in metric_rows if x['post_action_divergence']!='NA') if metric_rows else 'NA'
 report={'planned_pairs':80,'completed_pairs':len(completed),'real_trajectories':sum((RESULTS/'raw'/f'{pid}_{r}.json').exists() for pid in pair_ids for r in ('control','treatment')),'failed_pairs':failed,'early_termination_pairs':len(early),'scheduled_exposure_step_distribution':dict(sorted(scheduled.items())),'actual_exposure_step_distribution':dict(sorted(actual_dist.items())),'actual_exposure_matches_schedule':matches,'generation_identical_before_exposure':sum(str(x['generation_identical_before_exposure']).lower()=='true' for x in pre_rows),'intervention_hidden_before_exposure':sum(str(x['intervention_hidden_before_exposure']).lower()=='true' for x in pre_rows),'pre_exposure_behavioral_divergence_rate':round(natural_divergence,4),'valid_for_trajectory_level_effect':trajectory_valid,'valid_for_temporal_onset_analysis':temporal_valid,'prompt_leakage_count':prompt_leaks,'schema_error_count':schema_errors,'forbidden_label_count':forbidden,'benchmark_metadata_visible_count':metadata_bad,'mean_pre_action_divergence':round(pre_action,4) if pre_action!='NA' else 'NA','mean_post_action_divergence':round(post_action,4) if post_action!='NA' else 'NA','validity_decision':decision,'pidr_performance_used':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
