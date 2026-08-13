#!/usr/bin/env python3
import argparse,concurrent.futures,hashlib,json,os,shutil,subprocess,tempfile,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_transition_replication_v21';R=ROOT/'results/delegation_transition_replication_v21'
def verify():
 f=json.loads((B/'FROZEN_PROTOCOL_SHA256.json').read_text());bad=[]
 for rel,h in f['artifacts'].items():
  p=ROOT/rel
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(rel)
 if bad:raise SystemExit('frozen protocol mismatch: '+','.join(bad))
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--phase',choices=['preflight','full'],default='preflight');p.add_argument('--resume',action='store_true');p.add_argument('--model',default='gpt-5');p.add_argument('--max-workers',type=int,default=2);a=p.parse_args();verify();m=json.loads((B/'collection_manifest.json').read_text());jobs=m['jobs'];classes=['NO_BOUNDARY','SINGLE_BOUNDARY','REPEATED_SAME_BOUNDARY','SEQUENTIAL_NEW_BOUNDARIES']
 if a.phase=='preflight':
  chosen=[]
  for c in classes:chosen.append(next(x for x in jobs if x['condition']=='treatment' and x['intended_event_class']==c))
  jobs=chosen;outdir=R/'preflight/raw'
 else:outdir=R/'raw'
 outdir.mkdir(parents=True,exist_ok=True)
 if not a.execute:print(json.dumps({'phase':a.phase,'planned':len(jobs),'executed':False},indent=2));return
 if not os.environ.get('OPENAI_API_KEY'):raise SystemExit('OPENAI_API_KEY unavailable; no synthetic trajectories')
 def one(j):
  out=outdir/(j['trajectory_id']+'.json')
  if out.exists() and a.resume:return {'trajectory_id':j['trajectory_id'],'preserved':True,'ok':True}
  with tempfile.TemporaryDirectory(prefix='dtrv21_') as td:
   repo=Path(td)/'repo';shutil.copytree(ROOT/j['fixture_path'],repo);jp=Path(td)/'job.json';jp.write_text(json.dumps(j));cmd=['python3',str(ROOT/'runners/pre_action_coding_agent_v21.py'),'--job',str(jp),'--contract',str(B/'contracts'/f"{j['contract_id']}.json"),'--repository',str(repo),'--seed',str(j['seed']),'--model',a.model,'--output',str(out),'--max-steps',str(j['max_steps'])];d=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=j['timeout_seconds']);ok=d.returncode==0 and out.exists()
   if ok and a.phase=='preflight':
    freeze=R/'preflight/FIRST_REAL_ROLLOUT_FREEZE.json'
    if not freeze.exists():
     frozen=json.loads((B/'FROZEN_PROTOCOL_SHA256.json').read_text());freeze.write_text(json.dumps({'first_real_rollout_timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'first_real_rollout_id':j['trajectory_id'],'runner_hash':hashlib.sha256((ROOT/'runners/pre_action_coding_agent_v21.py').read_bytes()).hexdigest(),'scientific_component_hashes':frozen['artifacts'],'FIRST_REAL_ROLLOUT_FREEZE_ACTIVE':True},indent=2)+'\n')
   return {'trajectory_id':j['trajectory_id'],'ok':ok,'stderr':d.stderr[-1000:]}
 res=list(concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers).map(one,jobs));(R/'preflight'/'attempts.json' if a.phase=='preflight' else R/'attempts.json').write_text(json.dumps(res,indent=2)+'\n');
 if not all(x['ok'] for x in res):raise SystemExit('real trajectory failure; no replacement')
 if a.phase=='preflight':subprocess.run(['python3',str(ROOT/'experiments/audit_replication_v21_preflight.py')],cwd=ROOT,check=True)
if __name__=='__main__':main()
