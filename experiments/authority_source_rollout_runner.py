#!/usr/bin/env python3
"""Experiment 45: execute real control/treatment agent rollouts."""
from __future__ import annotations
import argparse,hashlib,json,shlex,shutil,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone

def tree_hash(root,excluded):
 h=hashlib.sha256()
 for path in sorted(x for x in root.rglob('*') if x.is_file() and str(x.relative_to(root)) not in excluded):h.update(str(path.relative_to(root)).encode());h.update(path.read_bytes())
 return h.hexdigest()
def jobs_from_manifest(data):
 if 'jobs' in data:return data['jobs']
 jobs=[]
 for pair in data.get('pairs',[]):
  for condition in ('control','treatment'):
   path=pair.get('trajectory_paths',{}).get(condition);jobs.append({'pair_id':pair['pair_id'],'condition':condition,'task_instruction':pair['task_instruction'],'seed':pair['seed'],'channel':pair['conditions'][condition]['environment_channel'],'environment_content':pair['conditions'][condition]['content'],'worktree':str(Path(pair['repository_fixture'])),'fixture_difference':[],'status':'MATERIALIZED' if Path(pair['repository_fixture']).exists() else 'NOT_READY','output':path})
 return jobs
def canonical(raw,job,repository,model):
 steps=raw.get('steps',raw.get('trajectory',[]));output=[]
 for index,event in enumerate(steps,1):output.append({'step':index,'action':event.get('action',event.get('command','')),'observation':event.get('observation',event.get('output','')),'tool':event.get('tool','unknown'),'timestamp':event.get('timestamp',datetime.now(timezone.utc).isoformat()),'observation_source':event.get('observation_source','UNKNOWN')})
 if not steps or any(not x['action'] for x in output):raise ValueError('runner trajectory is empty or lacks actions')
 return {'pair_id':job['pair_id'],'condition':job['condition'],'task':job['task_instruction'],'repository':str(repository),'seed':job['seed'],'model':model,'steps':output}
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=root/'results/authority_source_collection/collection_manifest.json');p.add_argument('--runner-command',required=True);p.add_argument('--model',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--output-dir',type=Path,default=root/'results/authority_source_collection');a=p.parse_args();data=json.loads(a.manifest.read_text());jobs=jobs_from_manifest(data);raw_dir=a.output_dir/'raw';failure_dir=a.output_dir/'failures';workspace_dir=a.output_dir/'rollout_workspaces';raw_dir.mkdir(parents=True,exist_ok=True);failure_dir.mkdir(parents=True,exist_ok=True);workspace_dir.mkdir(parents=True,exist_ok=True);records=[]
 if not a.execute:raise SystemExit('Refusing dry synthetic collection: pass --execute with a real runner command')
 for job in jobs:
  record={'pair_id':job['pair_id'],'condition':job['condition'],'status':'FAILED'};source=Path(job['worktree'])
  destination=raw_dir/f"{job['pair_id']}_{job['condition']}.json"
  if destination.exists():destination.unlink()
  if job.get('status') not in {'MATERIALIZED','COMPLETE'} or not source.exists():record['error']='workspace not materialized';records.append(record);continue
  workspace=Path(tempfile.mkdtemp(prefix=f"{job['pair_id']}_{job['condition']}_",dir=workspace_dir));repository=workspace/'repo';shutil.copytree(source,repository);temp_output=workspace/'runner_trajectory.json';command=a.runner_command.format(task=shlex.quote(job['task_instruction']),repo=shlex.quote(str(repository)),seed=job['seed'],output=shlex.quote(str(temp_output)),model=shlex.quote(a.model));completed=subprocess.run(command,shell=True,cwd=repository,text=True,capture_output=True);stderr_path=failure_dir/f"{job['pair_id']}_{job['condition']}.stderr";stderr_path.write_text(completed.stderr)
  if completed.returncode:record.update(error=f'runner exit {completed.returncode}',stderr=str(stderr_path));records.append(record);continue
  try:
   normalized=canonical(json.loads(temp_output.read_text()),job,repository,a.model);destination.write_text(json.dumps(normalized,indent=2));record.update(status='COMPLETE',trajectory=str(destination),stderr=str(stderr_path))
  except Exception as error:record.update(error=str(error),stderr=str(stderr_path))
  records.append(record)
 # Pair integrity is checked after execution without treating failures as data.
 grouped={}
 for job in jobs:grouped.setdefault(job['pair_id'],{})[job['condition']]=job
 integrity=[]
 for pair,conditions in grouped.items():
  if set(conditions)!={'control','treatment'}:continue
  excluded=set(conditions['control'].get('fixture_difference',[]))|set(conditions['treatment'].get('fixture_difference',[]));c,t=Path(conditions['control']['worktree']),Path(conditions['treatment']['worktree']);integrity.append({'pair_id':pair,'repository_hash_equal_excluding_injection':c.exists() and t.exists() and tree_hash(c,excluded)==tree_hash(t,excluded),'injection_only_files':sorted(excluded),'seed_match':conditions['control']['seed']==conditions['treatment']['seed']})
 report={'model':a.model,'jobs':records,'pair_integrity':integrity,'completed_jobs':sum(x['status']=='COMPLETE' for x in records),'completed_pairs':sum(all(any(x['pair_id']==pair and x['condition']==condition and x['status']=='COMPLETE' for x in records) for condition in ('control','treatment')) for pair in grouped)};(a.output_dir/'rollout_status.json').write_text(json.dumps(report,indent=2));print(json.dumps({'completed_jobs':report['completed_jobs'],'completed_pairs':report['completed_pairs'],'failed_jobs':len(records)-report['completed_jobs']},indent=2))
if __name__=='__main__':main()
