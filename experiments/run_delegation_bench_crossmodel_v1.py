#!/usr/bin/env python3
from __future__ import annotations
import argparse,concurrent.futures,json,shutil,subprocess,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));from delegation_bench_crossmodel_v1_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--split',choices=['smoke','fresh-sealed'],required=True);a.add_argument('--model',required=True);a.add_argument('--execute',action='store_true');a.add_argument('--resume',action='store_true');a.add_argument('--max-workers',type=int,default=2);z=a.parse_args()
 manifest=json.loads((BENCH/'collection_manifest.json').read_text()); split=json.loads((BENCH/'split.json').read_text()); allowed=split['development_smoke'] if z.split=='smoke' else split['fresh_sealed']
 if z.model not in MODELS.values():raise SystemExit('model not frozen')
 if z.split=='fresh-sealed' and not z.execute: print('fresh-sealed dry run only')
 if z.split=='fresh-sealed' and (RESULTS/'FRESH_SEALED_OPENED').exists():raise SystemExit('sealed already opened; use controlled evaluator workflow')
 jobs=[j for j in manifest['jobs'] if j['pair_id'] in allowed and j['model']==z.model];outroot=RESULTS/('smoke' if z.split=='smoke' else 'raw')/jkey(z.model);outroot.mkdir(parents=True,exist_ok=True)
 if not z.execute:print(json.dumps({'jobs':len(jobs),'output':str(outroot)},indent=2));return
 def one(j):
  out=outroot/f"{j['pair_id']}_{j['condition']}.json"
  if z.resume and out.exists():return 'RESUMED'
  work=Path(tempfile.mkdtemp(prefix='cmv1_',dir=RESULTS));env=work/'environment';shutil.copytree(j['initial_environment_path'],env);native=work/'native.json'
  cmd=['python3',str(ROOT/j['runner']),'--task',j['task'],'--environment',str(env),'--session-spec',j['session_spec'],'--seed',str(j['seed']),'--model',z.model,'--output',str(native),'--max-steps',str(j['max_steps'])]
  try:
   d=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=j['timeout_seconds']+30)
   if d.returncode or not native.exists():raise RuntimeError(d.stderr[-800:])
   value=json.loads(native.read_text());value.update({'pair_id':j['pair_id'],'condition':j['condition'],'paradigm':j['paradigm'],'task_family':j['task_family'],'intervention_style':j['intervention_style'],'fixture_sha256':j['fixture_sha256'],'synthetic':False});out.write_text(json.dumps(value,indent=2)+'\n');return 'COMPLETE'
  except Exception as e:(RESULTS/'qc').mkdir(exist_ok=True);(RESULTS/'qc'/f"{j['trajectory_id']}.failure.txt").write_text(str(e));return 'FAILED'
  finally:shutil.rmtree(work,ignore_errors=True)
 states=list(concurrent.futures.ThreadPoolExecutor(max_workers=z.max_workers).map(one,jobs));print(json.dumps({'jobs':len(jobs),'complete':sum(x in ('COMPLETE','RESUMED') for x in states),'failed':states.count('FAILED')},indent=2))
def jkey(model):return 'model_a' if model==MODELS['model_a'] else 'model_b'
if __name__=='__main__':main()
