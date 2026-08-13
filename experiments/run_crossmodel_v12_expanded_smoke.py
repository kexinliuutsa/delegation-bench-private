#!/usr/bin/env python3
from __future__ import annotations
import argparse,concurrent.futures,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'results/delegation_bench_crossmodel_v12/expanded_smoke'
def main():
 a=argparse.ArgumentParser();a.add_argument('--model',required=True,choices=['gpt-5','gpt-4.1']);a.add_argument('--execute',action='store_true');a.add_argument('--resume',action='store_true');a.add_argument('--max-workers',type=int,default=2);z=a.parse_args();m=json.loads((O/'smoke_manifest.json').read_text());jobs=[x for x in m['jobs'] if x['model']==z.model];key='model_a' if z.model=='gpt-5' else 'model_b';dest=O/'raw'/key
 def one(j):
  out=dest/f"{j['pair_id']}_{j['condition']}.json"
  if z.resume and out.exists():return 'RESUMED'
  w=Path(tempfile.mkdtemp(prefix='cmv12_',dir=O));env=w/'env';shutil.copytree(j['initial_environment_path'],env);native=w/'native.json'
  try:
   d=subprocess.run(['python3',str(ROOT/j['runner']),'--task',j['task'],'--environment',str(env),'--session-spec',j['session_spec'],'--seed',str(j['seed']),'--model',z.model,'--output',str(native),'--max-steps',str(j['max_steps'])],cwd=ROOT,capture_output=True,text=True,timeout=j['timeout_seconds']+30)
   if d.returncode or not native.exists():raise RuntimeError(d.stderr[-1000:])
   v=json.loads(native.read_text());v.update({'pair_id':j['pair_id'],'condition':j['condition'],'paradigm':j['paradigm'],'task_family':j['task_family'],'intervention_style':j['intervention_style'],'fixture_sha256':j['fixture_sha256'],'synthetic':False});out.write_text(json.dumps(v,indent=2)+'\n');return 'COMPLETE'
  except Exception as e:(O/f"{j['trajectory_id']}.failure.txt").write_text(str(e));return 'FAILED'
  finally:shutil.rmtree(w,ignore_errors=True)
 if not z.execute:print({'jobs':len(jobs)});return
 s=list(concurrent.futures.ThreadPoolExecutor(max_workers=z.max_workers).map(one,jobs));print(json.dumps({'jobs':len(jobs),'complete':sum(x in ('COMPLETE','RESUMED') for x in s),'failed':s.count('FAILED')},indent=2))
if __name__=='__main__':main()
