#!/usr/bin/env python3
"""Experiment 46: execute the 12 materialized pairs with a real coding agent."""
from __future__ import annotations
import argparse,hashlib,json,shlex,shutil,subprocess,sys,tempfile
from pathlib import Path
from runtime_rollout_audit import repository_snapshot

def tree_hash(root,excluded):
 h=hashlib.sha256()
 for p in sorted(x for x in root.rglob('*') if x.is_file() and str(x.relative_to(root)) not in excluded):h.update(str(p.relative_to(root)).encode());h.update(p.read_bytes())
 return h.hexdigest()
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=root/'results/authority_source_collection/collection_manifest.json');p.add_argument('--model',required=True);p.add_argument('--native-command',required=True,help='Real runner template using {task} {repo} {seed} {model} {output}');p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true',help='Keep parseable completed trajectories and run only missing jobs');p.add_argument('--output-dir',type=Path,default=root/'results/authority_source_collection');a=p.parse_args()
 if not a.execute:raise SystemExit('no real runner execution requested; pass --execute')
 manifest=json.loads(a.manifest.read_text());jobs=manifest.get('jobs',[]);pairs={x['pair_id'] for x in jobs};
 if len(pairs)!=12 or len(jobs)!=24:raise SystemExit(f'expected 12 materialized pairs/24 jobs, got {len(pairs)}/{len(jobs)}')
 raw=a.output_dir/'raw';failures=a.output_dir/'failures';workspaces=a.output_dir/'pilot_workspaces';snapshots=a.output_dir/'audit'/'snapshots';raw.mkdir(parents=True,exist_ok=True);failures.mkdir(parents=True,exist_ok=True);workspaces.mkdir(parents=True,exist_ok=True);snapshots.mkdir(parents=True,exist_ok=True);records=[];integrity=[];grouped={}
 for job in jobs:grouped.setdefault(job['pair_id'],{})[job['condition']]=job
 if not a.resume:
  for job in jobs:
   stale=raw/f"{job['pair_id']}_{job['condition']}.json"
   if stale.exists():stale.unlink()
 for pair,conditions in grouped.items():
  c,t=conditions['control'],conditions['treatment'];excluded=set(c['fixture_difference'])|set(t['fixture_difference']);checks={'pair_id':pair,'same_task':c['task_instruction']==t['task_instruction'],'same_seed':c['seed']==t['seed'],'same_agent_configuration':True,'repository_hash_equal_excluding_injection':tree_hash(Path(c['worktree']),excluded)==tree_hash(Path(t['worktree']),excluded),'injection_only_files':sorted(excluded)};integrity.append(checks)
  if not all((checks['same_task'],checks['same_seed'],checks['repository_hash_equal_excluding_injection'])):raise SystemExit(f'pair integrity failed before execution: {checks}')
 for job in jobs:
  destination=raw/f"{job['pair_id']}_{job['condition']}.json";stderr=failures/f"{job['pair_id']}_{job['condition']}.stderr"
  if a.resume and destination.exists():
   try:
    existing=json.loads(destination.read_text());valid=existing.get('pair_id')==job['pair_id'] and existing.get('condition')==job['condition'] and bool(existing.get('steps'))
   except (OSError,json.JSONDecodeError):valid=False
   if valid:
    records.append({'pair_id':job['pair_id'],'condition':job['condition'],'seed':job['seed'],'model':a.model,'status':'COMPLETE','trajectory':str(destination),'resumed':True});continue
  workspace=Path(tempfile.mkdtemp(prefix=f"{job['pair_id']}_{job['condition']}_",dir=workspaces));repo=workspace/'repo';shutil.copytree(job['worktree'],repo);initial=repository_snapshot(repo);(snapshots/f"{job['pair_id']}_{job['condition']}_initial.json").write_text(json.dumps(initial,indent=2));adapter_output=workspace/'adapter.json';command=[sys.executable,str(root/'runners/swe_agent_runner.py'),'--task',job['task_instruction'],'--repository',str(repo),'--seed',str(job['seed']),'--model',a.model,'--output',str(adapter_output),'--pair-id',job['pair_id'],'--condition',job['condition'],'--native-command',a.native_command,'--native-cwd',str(root)];completed=subprocess.run(command,text=True,capture_output=True);final=repository_snapshot(repo);(snapshots/f"{job['pair_id']}_{job['condition']}_final.json").write_text(json.dumps(final,indent=2));stderr.write_text(completed.stderr);record={'pair_id':job['pair_id'],'condition':job['condition'],'seed':job['seed'],'model':a.model,'status':'FAILED','stderr':str(stderr),'initial_hash':initial['hash'],'final_hash':final['hash']}
  if completed.returncode==0 and adapter_output.exists():shutil.copy2(adapter_output,destination);record.update(status='COMPLETE',trajectory=str(destination))
  else:record['error']=f'adapter exit {completed.returncode}'
  records.append(record)
 completed_pairs=sum(all(any(x['pair_id']==pair and x['condition']==condition and x['status']=='COMPLETE' for x in records) for condition in ('control','treatment')) for pair in pairs);status={'completed_pairs':completed_pairs,'failed_pairs':len(pairs)-completed_pairs,'trajectories':records,'pair_integrity':integrity,'model':a.model};(a.output_dir/'status.json').write_text(json.dumps(status,indent=2));(a.output_dir/'rollout_status.json').write_text(json.dumps({'completed_pairs':completed_pairs,'jobs':records,'pair_integrity':integrity},indent=2));subprocess.run([sys.executable,str(root/'experiments/runtime_rollout_audit.py'),'--manifest',str(a.manifest),'--raw-dir',str(raw),'--snapshots-dir',str(snapshots),'--output',str(a.output_dir/'audit'/'runtime_rollout_audit.json')],check=True)
 if completed_pairs>=10:
  subprocess.run([sys.executable,str(root/'experiments/authority_source_alignment.py')],check=True);subprocess.run([sys.executable,str(root/'experiments/pilot_quality_audit.py')],check=True);subprocess.run([sys.executable,str(root/'experiments/authority_source_evaluation.py')],check=True);subprocess.run([sys.executable,str(root/'experiments/pilot_authority_source_summary.py')],check=True)
 print(json.dumps({'completed_pairs':completed_pairs,'failed_pairs':len(pairs)-completed_pairs,'metrics_triggered':completed_pairs>=10},indent=2))
if __name__=='__main__':main()
