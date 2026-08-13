#!/usr/bin/env python3
import argparse,concurrent.futures,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_bench_crossmodel_v13';R=ROOT/'results/delegation_bench_crossmodel_v13/compatibility'
def main():
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--max-workers',type=int,default=2);a=p.parse_args();m=json.loads((B/'diagnostic_manifest.json').read_text());jobs=[x for x in m['jobs'] if x['model']==a.model]
 def one(j):
  w=Path(tempfile.mkdtemp(prefix='v13_',dir=R));env=w/'env';shutil.copytree(j['initial_environment_path'],env);out=R/'raw'/f"{j['trajectory_id']}.json";raw=R/'raw_proposals'/f"{j['trajectory_id']}.jsonl";dispatch=R/'dispatch'/f"{j['trajectory_id']}.jsonl"
  cmd=['python3',str(ROOT/j['runner']),'--paradigm',j['paradigm'],'--task',j['task'],'--environment',str(env),'--session-spec',j['session_spec'],'--seed',str(j['seed']),'--model',a.model,'--output',str(out),'--max-steps',str(j['max_steps']),'--pair-id',j['pair_id'],'--trajectory-id',j['trajectory_id'],'--condition',j['condition'],'--raw-log',str(raw),'--dispatch-log',str(dispatch)]
  try:d=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=210);return {'job':j,'ok':d.returncode==0 and out.exists(),'stderr':d.stderr}
  finally:shutil.rmtree(w,ignore_errors=True)
 if not a.execute:return
 res=list(concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers).map(one,jobs));(R/f'{a.model}_run.json').write_text(json.dumps([{'trajectory_id':x['job']['trajectory_id'],'ok':x['ok'],'stderr':x['stderr']} for x in res],indent=2)+'\n');print({'complete':sum(x['ok'] for x in res),'failed':sum(not x['ok'] for x in res)})
if __name__=='__main__':main()
