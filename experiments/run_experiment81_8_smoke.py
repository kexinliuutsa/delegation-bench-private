#!/usr/bin/env python3
import argparse,concurrent.futures,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_bench_crossmodel_v13';O=ROOT/'results/delegation_bench_crossmodel_v13/experiment81_8'
def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',choices=['A','B'],required=True);p.add_argument('--model',choices=['gpt-5','gpt-4.1'],required=True);p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--max-workers',type=int,default=2);a=p.parse_args();m=json.loads((B/f'experiment81_8_batch_{a.batch}_manifest.json').read_text());jobs=[j for j in m['jobs'] if j['model']==a.model];key='model_a' if a.model=='gpt-5' else 'model_b';root=O/f'batch_{a.batch}'
 def one(j):
  out=root/'raw'/key/f"{j['pair_id']}_{j['condition']}.json";raw=root/'raw_proposals'/f"{j['trajectory_id']}.jsonl";dispatch=root/'dispatch'/f"{j['trajectory_id']}.jsonl";failure=root/'failures'/f"{j['trajectory_id']}.json"
  if a.resume and out.exists():return {'trajectory_id':j['trajectory_id'],'status':'RESUMED'}
  work=Path(tempfile.mkdtemp(prefix='e818_',dir=root));env=work/'environment';shutil.copytree(j['initial_environment_path'],env)
  cmd=['python3',str(ROOT/j['runner']),'--paradigm',j['paradigm'],'--task',j['task'],'--environment',str(env),'--session-spec',j['session_spec'],'--seed',str(j['seed']),'--model',a.model,'--output',str(out),'--max-steps',str(j['max_steps']),'--pair-id',j['pair_id'],'--trajectory-id',j['trajectory_id'],'--condition',j['condition'],'--raw-log',str(raw),'--dispatch-log',str(dispatch)]
  try:
   d=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=j['timeout_seconds']+30)
   if d.returncode or not out.exists():
    failure.write_text(json.dumps({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'model':a.model,'returncode':d.returncode,'stderr':d.stderr[-4000:],'raw_log':str(raw),'dispatch_log':str(dispatch)},indent=2)+'\n');return {'trajectory_id':j['trajectory_id'],'status':'FAILED'}
   return {'trajectory_id':j['trajectory_id'],'status':'COMPLETE'}
  except Exception as e:
   failure.write_text(json.dumps({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'model':a.model,'exception_type':type(e).__name__,'exception_message':str(e),'raw_log':str(raw),'dispatch_log':str(dispatch)},indent=2)+'\n');return {'trajectory_id':j['trajectory_id'],'status':'FAILED'}
  finally:shutil.rmtree(work,ignore_errors=True)
 if not a.execute:print({'planned':len(jobs)});return
 rows=list(concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers).map(one,jobs));(root/f'{key}_collection_status.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({'planned':len(rows),'complete':sum(x['status'] in ('COMPLETE','RESUMED') for x in rows),'failed':sum(x['status']=='FAILED' for x in rows)},indent=2))
if __name__=='__main__':main()
