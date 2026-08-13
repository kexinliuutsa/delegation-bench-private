#!/usr/bin/env python3
"""Hard-fail generation-isolation audit for Delegation Bench v1."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from delegation_bench_v1_common import ROOT,BENCH,RESULTS,file_hashes,sha
FIELDS=['task','task_family','seed','agent_model','runner','runner_version','runner_source_sha256','runner_dependency_sha256','system_prompt','system_prompt_sha256','tool_schema','tool_schema_sha256','max_steps','timeout_seconds','model_api_configuration','sampling_configuration','tool_permissions','prompt_prefix','prompt_suffix','workspace_snapshot','workspace_snapshot_sha256','scheduled_exposure_step','pre_exposure_end_step']
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=BENCH/'collection_manifest.json');p.add_argument('--output-dir',type=Path,default=RESULTS/'audits');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True);manifest=json.loads(a.manifest.read_text());pairs={}
 for job in manifest['jobs']:pairs.setdefault(job['pair_id'],{})[job['condition']]=job
 rows=[]
 for pid,roles in sorted(pairs.items()):
  c,t=roles['control'],roles['treatment'];unknown=[];mismatch=[]
  for field in FIELDS:
   if field not in c or field not in t:unknown.append(field)
   elif c[field]!=t[field]:mismatch.append(field)
  fixture=Path(c['initial_environment_path']);actual=file_hashes(fixture);snapshot_ok=actual==c.get('workspace_snapshot')==t.get('workspace_snapshot') and sha(actual)==c.get('workspace_snapshot_sha256')==t.get('workspace_snapshot_sha256')
  if not snapshot_ok:mismatch.append('materialized_workspace_snapshot')
  cs=json.loads(Path(c['session_spec']).read_text());ts=json.loads(Path(t['session_spec']).read_text());allowed={'payload_at_boundary','second_payload'};session_unexpected=[k for k in set(cs)|set(ts) if cs.get(k)!=ts.get(k) and k not in allowed]
  mismatch.extend('session_spec.'+x for x in session_unexpected);declared_only=not session_unexpected and cs.get('payload_at_boundary')!=ts.get('payload_at_boundary')
  status='VALID_GENERATION_ISOLATION' if not mismatch and not unknown and declared_only else ('INVALID_PRETREATMENT_MISMATCH' if mismatch else 'UNKNOWN_METADATA')
  rows.append({'pair_id':pid,'paradigm':c['paradigm'],'task_equal':c.get('task')==t.get('task'),'seed_equal':c.get('seed')==t.get('seed'),'model_equal':c.get('agent_model')==t.get('agent_model'),'runner_equal':c.get('runner')==t.get('runner') and c.get('runner_source_sha256')==t.get('runner_source_sha256'),'system_prompt_equal':c.get('system_prompt_sha256')==t.get('system_prompt_sha256'),'tool_schema_equal':c.get('tool_schema_sha256')==t.get('tool_schema_sha256'),'initial_environment_equal':snapshot_ok,'non_intervention_artifacts_equal':snapshot_ok,'sampling_equal':c.get('sampling_configuration')==t.get('sampling_configuration'),'timeout_equal':c.get('timeout_seconds')==t.get('timeout_seconds'),'max_steps_equal':c.get('max_steps')==t.get('max_steps'),'declared_intervention_only':declared_only,'unknown_fields':'|'.join(unknown),'unexpected_fields':'|'.join(mismatch),'pair_status':status})
 with (a.output_dir/'generation_isolation.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 passed=sum(x['pair_status']=='VALID_GENERATION_ISOLATION' for x in rows);summary={'planned_pairs':len(rows),'passed_pairs':passed,'invalid_pairs':sum(x['pair_status']=='INVALID_PRETREATMENT_MISMATCH' for x in rows),'unknown_pairs':sum(x['pair_status']=='UNKNOWN_METADATA' for x in rows),'pass_rate':passed/len(rows),'hard_fail':passed!=len(rows),'all_pairs_generation_isolated':passed==len(rows)};(a.output_dir/'generation_isolation_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
