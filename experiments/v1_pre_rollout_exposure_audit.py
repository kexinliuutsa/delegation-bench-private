#!/usr/bin/env python3
"""Verify all v1 intervention payloads are absent from agent-visible pre-rollout state."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from delegation_bench_v1_common import BENCH,RESULTS
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=BENCH/'collection_manifest.json');p.add_argument('--output',type=Path,default=RESULTS/'audits/pre_rollout_exposure_audit.json');a=p.parse_args();m=json.loads(a.manifest.read_text());pairs={}
 for job in m['jobs']:pairs.setdefault(job['pair_id'],{})[job['condition']]=job
 audits=[]
 for pid,roles in sorted(pairs.items()):
  c,t=roles['control'],roles['treatment'];session=json.loads(Path(t['session_spec']).read_text());payloads=[x for x in (session['payload_at_boundary'],session.get('second_payload')) if x];root=Path(t['initial_environment_path']);files=[x for x in root.rglob('*') if x.is_file()];visible={'task':t['task'],'system_prompt':t['system_prompt'],'tool_schema':json.dumps(t['tool_schema'],sort_keys=True),'initial_file_contents':'\n'.join(x.read_text(errors='replace') for x in files),'initial_filenames':'\n'.join(str(x.relative_to(root)) for x in files),'agent_visible_metadata':json.dumps({'task':t['task'],'seed':t['seed'],'model':t['agent_model']},sort_keys=True)};leaks={field:[payload for payload in payloads if payload in text] for field,text in visible.items()};leaks={k:v for k,v in leaks.items() if v};passed=not leaks and c['workspace_snapshot_sha256']==t['workspace_snapshot_sha256'] and c['scheduled_exposure_step']==t['scheduled_exposure_step']
  audits.append({'pair_id':pid,'paradigm':t['paradigm'],'scheduled_exposure_step':t['scheduled_exposure_step'],'pass':passed,'leak_locations':leaks,'schedule_runner_private':True})
 passed=sum(x['pass'] for x in audits);report={'benchmark_version':'v1','planned_pairs':len(audits),'passed_pairs':passed,'failed_pairs':len(audits)-passed,'all_pairs_pass':passed==len(audits),'intervention_schedule_location':'runner-private session spec only','audits':audits};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('planned_pairs','passed_pairs','failed_pairs','all_pairs_pass')},indent=2))
if __name__=='__main__':main()
