#!/usr/bin/env python3
"""Frozen v1.3 fresh-sealed collector. Experiment 81.9 does not execute this file."""
import argparse,concurrent.futures,json,shutil,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_bench_crossmodel_v13/fresh_sealed_v13';R=ROOT/'results/delegation_bench_crossmodel_v13/fresh_sealed'
def main():
 p=argparse.ArgumentParser();p.add_argument('--model',choices=['gpt-5','gpt-4.1'],required=True);p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--max-workers',type=int,default=2);a=p.parse_args();m=json.load(open(B/'collection_manifest.json'));jobs=[j for j in m['jobs'] if j['model']==a.model];key='model_a' if a.model=='gpt-5' else 'model_b'
 if not a.execute:print(json.dumps({'planned':len(jobs),'fresh_sealed_opened':(R/'FRESH_SEALED_OPENED').exists()}));return
 marker=R/'FRESH_SEALED_OPENED';R.mkdir(parents=True,exist_ok=True)
 if not marker.exists():raise SystemExit('FRESH_SEALED_OPENED marker must be created and verified immediately before collection')
 def one(j):
  out=R/'raw'/key/f"{j['pair_id']}_{j['condition']}.json";raw=R/'raw_proposals'/f"{j['trajectory_id']}.jsonl";dispatch=R/'dispatch'/f"{j['trajectory_id']}.jsonl";failure=R/'failures'/f"{j['trajectory_id']}.json"
  if a.resume and out.exists():return 'RESUMED'
  work=Path(tempfile.mkdtemp(prefix='v13sealed_',dir=R));env=work/'environment';shutil.copytree(j['initial_environment_path'],env)
  cmd=['python3',str(ROOT/j['runner']),'--paradigm',j['paradigm'],'--task',j['task'],'--environment',str(env),'--session-spec',j['session_spec'],'--seed',str(j['seed']),'--model',a.model,'--output',str(out),'--max-steps',str(j['max_steps']),'--pair-id',j['pair_id'],'--trajectory-id',j['trajectory_id'],'--condition',j['condition'],'--raw-log',str(raw),'--dispatch-log',str(dispatch)]
  try:
   d=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=240)
   if d.returncode or not out.exists():failure.parent.mkdir(parents=True,exist_ok=True);failure.write_text(json.dumps({'trajectory_id':j['trajectory_id'],'stderr':d.stderr[-4000:],'raw_log':str(raw),'dispatch_log':str(dispatch)},indent=2)+'\n');return 'FAILED'
   return 'COMPLETE'
  finally:shutil.rmtree(work,ignore_errors=True)
 for d in ('raw/'+key,'raw_proposals','dispatch','failures'):(R/d).mkdir(parents=True,exist_ok=True)
 result=list(concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers).map(one,jobs));print(json.dumps({'planned':len(result),'complete':sum(x in ('COMPLETE','RESUMED') for x in result),'failed':result.count('FAILED')},indent=2))
if __name__=='__main__':main()
