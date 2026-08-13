#!/usr/bin/env python3
"""Experiment 60 runner: execute real Web-agent rollouts from Experiment 59."""
from __future__ import annotations
import argparse,concurrent.futures,json,shlex,subprocess,tempfile
from pathlib import Path

def valid(path,job,model):
 try:value=json.loads(path.read_text())
 except (OSError,json.JSONDecodeError):return False
 return value.get('task')==job['task'] and value.get('seed')==job['seed'] and value.get('model')==model and bool(value.get('steps'))
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();base=root/'results/web_delegation';p.add_argument('--manifest',type=Path,default=base/'collection_manifest.json');p.add_argument('--output-dir',type=Path,default=base);p.add_argument('--model',required=True);p.add_argument('--native-command',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
 if not a.execute:raise SystemExit('--execute required: synthetic trajectories are forbidden')
 if not 1<=a.workers<=8:raise SystemExit('--workers must be 1..8')
 forbidden=('{pair_id}','{condition}','{injection','{intervention','{experiment')
 if any(x in a.native_command.lower() for x in forbidden):raise SystemExit('native command leaks experimental metadata')
 manifest=json.loads(a.manifest.read_text());jobs=manifest['jobs']
 if manifest.get('pair_count')!=48 or len(jobs)!=96:raise SystemExit('fixed web protocol requires 48 pairs / 96 trajectories')
 raw=a.output_dir/'raw';failures=a.output_dir/'failures';workspaces=a.output_dir/'rollout_workspaces'
 for path in (raw,failures,workspaces):path.mkdir(parents=True,exist_ok=True)
 if not a.resume and any(raw.glob('*.json')):raise SystemExit('raw data exists; use --resume')
 def run(job):
  destination=raw/f'{job["pair_id"]}_{job["condition"]}.json'
  if a.resume and valid(destination,job,a.model):return {'pair_id':job['pair_id'],'condition':job['condition'],'status':'COMPLETE','resumed':True}
  workspace=Path(tempfile.mkdtemp(prefix='web60_',dir=workspaces));native=workspace/'native.json';command=a.native_command.format(task=shlex.quote(job['task']),site=shlex.quote(job['site']),seed=job['seed'],model=shlex.quote(a.model),output=shlex.quote(str(native)));completed=subprocess.run(command,shell=True,cwd=root,text=True,capture_output=True);(failures/f'{job["pair_id"]}_{job["condition"]}.stderr').write_text(completed.stderr)
  try:
   if completed.returncode or not native.exists():raise RuntimeError(f'native runner failed ({completed.returncode})')
   value=json.loads(native.read_text());normalized={'task':job['task'],'seed':job['seed'],'model':a.model,'steps':[{"step":i,"tool":e.get('tool','unknown'),"action":e.get('action',''),"observation":e.get('observation',''),"observation_source":e.get('observation_source','UNKNOWN')} for i,e in enumerate(value.get('steps',[]),1)]}
   if not normalized['steps']:raise RuntimeError('no real actions')
   destination.write_text(json.dumps(normalized,indent=2)+'\n');return {'pair_id':job['pair_id'],'condition':job['condition'],'status':'COMPLETE','trajectory':str(destination)}
  except Exception as error:return {'pair_id':job['pair_id'],'condition':job['condition'],'status':'FAILED','error':str(error)}
 records=list(map(run,jobs)) if a.workers==1 else list(concurrent.futures.ThreadPoolExecutor(max_workers=a.workers).map(run,jobs));complete=sum(x['status']=='COMPLETE' for x in records);pairs=sum(all(any(x['pair_id']==pair and x['condition']==condition and x['status']=='COMPLETE' for x in records) for condition in ('control','treatment')) for pair in {x['pair_id'] for x in jobs});status={'agent_type':'web','model':a.model,'expected_trajectories':96,'completed_trajectories':complete,'completed_pairs':pairs,'labels_generated':False,'jobs':records};(a.output_dir/'rollout_status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps({k:status[k] for k in ('completed_trajectories','completed_pairs','labels_generated')},indent=2))
if __name__=='__main__':main()
