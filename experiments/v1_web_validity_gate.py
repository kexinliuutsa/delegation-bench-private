#!/usr/bin/env python3
"""Web cohort validity report symmetric to the Coding validity gate."""
from __future__ import annotations
import collections,csv,json
from pathlib import Path
from statistics import mean
from delegation_bench_v1_common import BENCH,RESULTS
def main():
 manifest=json.loads((BENCH/'collection_manifest.json').read_text());pairs=[p for p in manifest['pairs'] if p['paradigm']=='web'];raw=RESULTS/'raw';pre={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/pre_exposure_prefix_audit.csv').open())};gen={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/generation_isolation.csv').open())};metrics={r['pair_id']:r for r in csv.DictReader((RESULTS/'measurements/pair_measurements.csv').open())};complete=[];early=[];actual=[]
 for pair in pairs:
  paths=[raw/f"{pair['pair_id']}_{role}.json" for role in ('control','treatment')]
  if not all(p.exists() for p in paths):continue
  complete.append(pair);values=[json.loads(p.read_text()) for p in paths]
  if any(v.get('early_termination') for v in values):early.append(pair['pair_id'])
  audited=pre.get(pair['pair_id'],{}).get('actual_exposure_step','');actual.append(int(audited) if audited.isdigit() else None)
 rows=[pre[p['pair_id']] for p in complete];mr=[metrics[p['pair_id']] for p in complete if p['pair_id'] in metrics];report={'planned_pairs':80,'completed_pairs':len(complete),'pair_completion':f'{len(complete)}/80','exposure_schedule_matches':sum(a==p['scheduled_exposure_step'] for a,p in zip(actual,complete)),'generation_isolation_passes':sum(gen[p['pair_id']]['pair_status']=='VALID_GENERATION_ISOLATION' for p in complete),'intervention_hidden_before_exposure':sum(r['intervention_hidden_before_exposure'].lower()=='true' for r in rows),'early_termination_pairs':len(early),'pre_exposure_behavioral_divergence_rate':round(mean(r['behaviorally_diverged_before_exposure'].lower()=='true' for r in rows),4) if rows else 0,'valid_temporal_onset_pairs':sum(r['valid_for_temporal_onset_analysis'].lower()=='true' for r in rows),'mean_pre_action_divergence':round(mean(float(r['pre_action_divergence']) for r in mr if r['pre_action_divergence']!='NA'),4) if mr else 'NA','mean_post_action_divergence':round(mean(float(r['post_action_divergence']) for r in mr if r['post_action_divergence']!='NA'),4) if mr else 'NA'};(RESULTS/'audits/web_validity_gate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
