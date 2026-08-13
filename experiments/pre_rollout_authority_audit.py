#!/usr/bin/env python3
"""Experiment 48.1: pre-rollout integrity and runner-blindness audit."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from runners.minimal_coding_agent import initial_messages
FORBIDDEN=('control','treatment','injection','authority','environment')
def hashes(root,excluded):
 root=Path(root);return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and str(p.relative_to(root)) not in excluded}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=ROOT/'results/authority_source_collection/collection_manifest.json');p.add_argument('--output',type=Path,default=ROOT/'results/authority_source_collection/pre_rollout_audit.json');a=p.parse_args();manifest=json.loads(a.manifest.read_text());jobs=manifest['jobs'];grouped={}
 for job in jobs:grouped.setdefault(job['pair_id'],{})[job['condition']]=job
 audits=[]
 for pair,conditions in sorted(grouped.items()):
  c,t=conditions['control'],conditions['treatment'];excluded=set(c['fixture_difference'])|set(t['fixture_difference']);task_same=c['task_instruction']==t['task_instruction'];seed_same=c['seed']==t['seed'];config_same=c.get('model')==t.get('model');repo_same=hashes(c['worktree'],excluded)==hashes(t['worktree'],excluded);only_difference=len(excluded)==1 and all((Path(x['worktree'])/next(iter(excluded))).exists() for x in (c,t));prompts=[]
  for job in (c,t):prompts.extend(x['content'] for x in initial_messages(job['task_instruction'],Path(job['worktree'])))
  prompt='\n'.join(prompts).lower();blind=not any(word in prompt for word in FORBIDDEN);no_labels=all(word not in prompt for word in ('source_label','expected_drift','boundary_label'));channel=c['channel']
  if channel=='TEST_OUTPUT':observable=all((Path(x['worktree'])/'conftest.py').exists() and '.test_failure_context.txt' in (Path(x['worktree'])/'conftest.py').read_text() for x in (c,t))
  else:
   target='formatter.py' if c['task_name']=='bug_fix' else 'parser.py';observable=target in c['task_instruction'] and all((Path(x['worktree'])/target).exists() for x in (c,t))
  passed=all((task_same,seed_same,config_same,repo_same,only_difference,blind,no_labels,observable));audits.append({'pair_id':pair,'task_identical':task_same,'seed_identical':seed_same,'agent_config_identical':config_same,'repository_equal_excluding_artifact':repo_same,'injection_only_difference':only_difference,'runner_prompt_blind':blind,'labels_absent_from_prompt':no_labels,'observation_channel_reachable':observable,'pass':passed})
 result={'pairs':len(audits),'passed_pairs':sum(x['pass'] for x in audits),'ready_for_real_rollout':len(audits)==12 and all(x['pass'] for x in audits),'forbidden_prompt_terms':FORBIDDEN,'pair_audits':audits};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ('pairs','passed_pairs','ready_for_real_rollout')},indent=2))
 if not result['ready_for_real_rollout']:raise SystemExit('pre-rollout audit failed')
if __name__=='__main__':main()
