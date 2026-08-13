#!/usr/bin/env python3
"""Normalize completed real v1 rollouts into the universal trajectory schema."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from delegation_bench_v1_common import BENCH,RESULTS,CAPABILITIES
BANNED={'attack_label','unsafe_label','authority_label','drift_label','source_label','oracle_label','private_reasoning','chain_of_thought'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=BENCH/'collection_manifest.json');p.add_argument('--raw-dir',type=Path,default=RESULTS/'raw');p.add_argument('--output',type=Path,default=RESULTS/'normalized/trajectories.jsonl');a=p.parse_args();manifest=json.loads(a.manifest.read_text());rows=[]
 exposure_audit=RESULTS/'audits/pre_exposure_prefix_audit.csv'
 reconstructed={}
 if exposure_audit.exists():
  reconstructed={row['pair_id']:row['actual_exposure_step'] for row in csv.DictReader(exposure_audit.open())}
 for job in manifest['jobs']:
  path=a.raw_dir/f"{job['pair_id']}_{job['condition']}.json"
  if not path.exists():continue
  raw=json.loads(path.read_text());steps=[]
  for event in raw.get('steps',[]):
   step={k:event.get(k,'') for k in ('step','tool','action','arguments','observation','observation_source','capability_state','environment_snapshot_hash')}
   if step['capability_state'] not in CAPABILITIES:raise ValueError(f"invalid capability state in {path}: {step['capability_state']}")
   steps.append(step)
  audited=reconstructed.get(job['pair_id'],'')
  actual=int(audited) if audited.isdigit() else None
  row={'benchmark_version':'v1','pair_id':job['pair_id'],'trajectory_id':job['trajectory_id'],'paradigm':job['paradigm'],'task_family':job['task_family'],'task':job['task'],'seed':job['seed'],'condition':job['condition'],'agent_id':job['agent_id'],'agent_model':raw['model'],'runner_version':job['runner_version'],'scheduled_exposure_step':job['scheduled_exposure_step'],'pre_exposure_end_step':job['pre_exposure_end_step'],'actual_exposure_step':actual,'completion_status':'EARLY_TERMINATION' if raw.get('early_termination') else ('COMPLETE' if raw.get('finished') else 'MAX_STEPS_OR_INCOMPLETE'),'steps':steps}
  if BANNED & set(row):raise ValueError('forbidden label/reasoning field')
  rows.append(row)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in rows));print(json.dumps({'normalized_real_trajectories':len(rows),'synthetic_trajectories':0,'labels_generated':False},indent=2))
if __name__=='__main__':main()
