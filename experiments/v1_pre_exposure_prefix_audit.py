#!/usr/bin/env python3
"""Audit delayed exposure on completed real Benchmark v1 pairs."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from delegation_bench_v1_common import BENCH,RESULTS
COLS=['pair_id','paradigm','scheduled_exposure_step','actual_exposure_step','generation_identical_before_exposure','intervention_hidden_before_exposure','behaviorally_diverged_before_exposure','valid_for_trajectory_level_effect','valid_for_temporal_onset_analysis']
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=BENCH/'collection_manifest.json');p.add_argument('--raw-dir',type=Path,default=RESULTS/'raw');p.add_argument('--output',type=Path,default=RESULTS/'audits/pre_exposure_prefix_audit.csv');a=p.parse_args();manifest=json.loads(a.manifest.read_text());pairs={}
 for job in manifest['jobs']:pairs.setdefault(job['pair_id'],{})[job['condition']]=job
 generation={x['pair_id']:x for x in csv.DictReader((RESULTS/'audits/generation_isolation.csv').open())};rows=[]
 for pid,roles in sorted(pairs.items()):
  paths={r:a.raw_dir/f'{pid}_{r}.json' for r in ('control','treatment')}
  if not all(x.exists() for x in paths.values()):continue
  raw={r:json.loads(x.read_text()) for r,x in paths.items()};scheduled=int(roles['control']['scheduled_exposure_step']);session=json.loads(Path(roles['treatment']['session_spec']).read_text());payloads=[x for x in (session['payload_at_boundary'],session.get('second_payload')) if x];pre_t=raw['treatment'].get('steps',[])[:scheduled-1];hidden=all(all(payload not in str(x.get('observation','')) for payload in payloads) for x in pre_t);actual=next((int(x['step']) for x in raw['treatment'].get('steps',[]) if any(payload in str(x.get('observation','')) for payload in payloads)),None);cpre=raw['control'].get('steps',[])[:scheduled-1];diverged=len(cpre)!=len(pre_t) or any((x.get('tool'),x.get('action'))!=(y.get('tool'),y.get('action')) for x,y in zip(cpre,pre_t));runtime_snapshots_equal=len(cpre)==len(pre_t) and all(x.get('environment_snapshot_hash')==y.get('environment_snapshot_hash') for x,y in zip(cpre,pre_t));generation_ok=generation.get(pid,{}).get('pair_status')=='VALID_GENERATION_ISOLATION';trajectory_valid=generation_ok and hidden;temporal=trajectory_valid and actual is not None
  rows.append({'pair_id':pid,'paradigm':roles['control']['paradigm'],'scheduled_exposure_step':scheduled,'actual_exposure_step':actual if actual is not None else 'EARLY_TERMINATION' if raw['treatment'].get('early_termination') else 'NOT_OBSERVED','generation_identical_before_exposure':generation_ok,'intervention_hidden_before_exposure':hidden,'behaviorally_diverged_before_exposure':diverged,'valid_for_trajectory_level_effect':trajectory_valid,'valid_for_temporal_onset_analysis':temporal,'_runtime_snapshots_equal':runtime_snapshots_equal})
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows([{k:v for k,v in x.items() if not k.startswith('_')} for x in rows])
 summary={'completed_pairs_audited':len(rows),'generation_identical_pairs':sum(x['generation_identical_before_exposure'] for x in rows),'runtime_pre_exposure_snapshot_equal_pairs':sum(x['_runtime_snapshots_equal'] for x in rows),'runtime_snapshot_difference_may_follow_stochastic_actions':True,'intervention_hidden_pairs':sum(x['intervention_hidden_before_exposure'] for x in rows),'pre_exposure_behavioral_divergence_pairs':sum(x['behaviorally_diverged_before_exposure'] for x in rows),'trajectory_level_valid_pairs':sum(x['valid_for_trajectory_level_effect'] for x in rows),'temporal_onset_valid_pairs':sum(x['valid_for_temporal_onset_analysis'] for x in rows)};(a.output.with_suffix('.summary.json')).write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
