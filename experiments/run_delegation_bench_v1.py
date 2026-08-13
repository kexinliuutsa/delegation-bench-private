#!/usr/bin/env python3
"""Collection orchestrator for real Delegation Bench v1 trajectories."""
from __future__ import annotations
import argparse,concurrent.futures,json,shlex,shutil,subprocess,tempfile,threading
from pathlib import Path
from delegation_bench_v1_common import ROOT,BENCH,RESULTS

def valid(path,job,model):
 try:d=json.loads(path.read_text())
 except Exception:return False
 return d.get('task')==job['task'] and d.get('seed')==job['seed'] and d.get('model')==model and isinstance(d.get('steps'),list) and bool(d['steps'])
def write_status(manifest):
 jobs=manifest['jobs'];complete=[j for j in jobs if (RESULTS/'raw'/f"{j['pair_id']}_{j['condition']}.json").exists()];pair_ids={j['pair_id'] for j in jobs};completed=sum(all((RESULTS/'raw'/f'{pid}_{r}.json').exists() for r in ('control','treatment')) for pid in pair_ids);counts={p:sum(1 for pid in pair_ids if next(j for j in jobs if j['pair_id']==pid)['paradigm']==p and all((RESULTS/'raw'/f'{pid}_{r}.json').exists() for r in ('control','treatment'))) for p in ('coding','web')};gen=json.loads((RESULTS/'audits/generation_isolation_summary.json').read_text()) if (RESULTS/'audits/generation_isolation_summary.json').exists() else {};pre=json.loads((RESULTS/'audits/pre_exposure_prefix_audit.summary.json').read_text()) if (RESULTS/'audits/pre_exposure_prefix_audit.summary.json').exists() else {};core_complete=counts['coding']==80 and counts['web']==80;ready=core_complete and gen.get('all_pairs_generation_isolated',False) and pre.get('trajectory_level_valid_pairs',0)>=160 and (BENCH/'split.json').exists() and (BENCH/'statistical_plan.json').exists()
 banned={'attack_label','unsafe_label','authority_label','drift_label','source_label','oracle_label','private_reasoning','chain_of_thought'}
 def leaked(value):
  if isinstance(value,dict):return bool(banned&set(value)) or any(leaked(x) for x in value.values())
  if isinstance(value,list):return any(leaked(x) for x in value)
  return False
 label_clean=True
 for job in complete:
  try:label_clean=label_clean and not leaked(json.loads((RESULTS/'raw'/f"{job['pair_id']}_{job['condition']}.json").read_text()))
  except Exception:label_clean=False
 ready=ready and label_clean
 previous=json.loads((RESULTS/'status.json').read_text()) if (RESULTS/'status.json').exists() else {}
 status={'planned_pairs':160,'planned_trajectories':320,'completed_pairs':completed,'completed_trajectories':len(complete),'coding_pairs':counts['coding'],'web_pairs':counts['web'],'generation_isolation_pass_rate':gen.get('pass_rate',0),'pre_exposure_valid_pairs':pre.get('trajectory_level_valid_pairs',0),'temporal_onset_valid_pairs':pre.get('temporal_onset_valid_pairs',0),'benchmark_ready':ready,'collection_status':'COMPLETE' if core_complete else 'COMPLETE_WITH_PERSISTENT_MISSINGNESS','future_transfer_paradigm':'UNASSIGNED','future_transfer_data_collected':False,'synthetic_trajectories':0,'label_leakage_detected':not label_clean,'labels_generated':False}
 if 'web_recovery' in previous:status['web_recovery']=previous['web_recovery']
 (RESULTS/'status.json').write_text(json.dumps(status,indent=2)+'\n');return status
def main():
 p=argparse.ArgumentParser();p.add_argument('--paradigm',choices=['coding','web','all'],default='all');p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--model');p.add_argument('--runner-command',help='Optional template: {runner} {task} {environment} {session_spec} {seed} {model} {output} {max_steps}');p.add_argument('--max-workers',type=int,default=1);a=p.parse_args();subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,check=True);manifest=json.loads((BENCH/'collection_manifest.json').read_text());subprocess.run(['python3',str(ROOT/'experiments/v1_generation_isolation_audit.py')],cwd=ROOT,check=True);gen=json.loads((RESULTS/'audits/generation_isolation_summary.json').read_text())
 if gen['hard_fail']:raise SystemExit('generation isolation hard-fail: invalid or unknown pair metadata')
 if not a.execute:subprocess.run(['python3',str(ROOT/'experiments/v1_pre_exposure_prefix_audit.py')],cwd=ROOT,check=True);print(json.dumps(write_status(manifest),indent=2));return
 if not a.model:raise SystemExit('--model is required with --execute')
 if a.model!='gpt-5':raise SystemExit('frozen v1 model configuration requires --model gpt-5')
 if not 1<=a.max_workers<=8:raise SystemExit('--max-workers must be 1..8')
 selected=[j for j in manifest['jobs'] if a.paradigm=='all' or j['paradigm']==a.paradigm];audit_lock=threading.Lock()
 def audit_if_pair_complete(job):
  if not all((RESULTS/'raw'/f"{job['pair_id']}_{role}.json").exists() for role in ('control','treatment')):return True
  with audit_lock:
   generation=subprocess.run(['python3',str(ROOT/'experiments/v1_generation_isolation_audit.py')],cwd=ROOT,capture_output=True,text=True)
   prefix=subprocess.run(['python3',str(ROOT/'experiments/v1_pre_exposure_prefix_audit.py')],cwd=ROOT,capture_output=True,text=True)
   if generation.returncode or prefix.returncode:
    (RESULTS/'audits'/f"{job['pair_id']}.audit_failure.txt").write_text(generation.stderr+'\n'+prefix.stderr);return False
  return True
 def execute(job):
  destination=RESULTS/'raw'/f"{job['pair_id']}_{job['condition']}.json"
  if a.resume and valid(destination,job,a.model):return 'RESUMED'
  if destination.exists():destination.unlink()
  work=Path(tempfile.mkdtemp(prefix='v1_',dir=RESULTS/'manifests'));environment=work/'environment';shutil.copytree(job['initial_environment_path'],environment);native=work/'native.json';runner=ROOT/job['runner']
  if a.runner_command:command=a.runner_command.format(runner=shlex.quote(str(runner)),task=shlex.quote(job['task']),environment=shlex.quote(str(environment)),session_spec=shlex.quote(job['session_spec']),seed=job['seed'],model=shlex.quote(a.model),output=shlex.quote(str(native)),max_steps=job['max_steps'])
  else:command=f"python3 {shlex.quote(str(runner))} --task {shlex.quote(job['task'])} --environment {shlex.quote(str(environment))} --session-spec {shlex.quote(job['session_spec'])} --seed {job['seed']} --model {shlex.quote(a.model)} --output {shlex.quote(str(native))} --max-steps {job['max_steps']}"
  try:
   done=subprocess.run(command,shell=True,cwd=ROOT,text=True,capture_output=True,timeout=job['timeout_seconds']+30)
   if done.returncode or not native.exists():raise RuntimeError(done.stderr[-1000:] or f'exit {done.returncode}')
   value=json.loads(native.read_text());destination.write_text(json.dumps(value,indent=2)+'\n');return 'COMPLETE' if audit_if_pair_complete(job) else 'COMPLETE_AUDIT_FAILED'
  except Exception as exc:
   if destination.exists():destination.unlink()
   stderr=getattr(locals().get('done'), 'stderr', '') or ''
   (RESULTS/'audits'/f"{job['trajectory_id']}.failure.txt").write_text(f'{type(exc).__name__}: {exc}\n{stderr}')
   return 'FAILED'
  finally:shutil.rmtree(work,ignore_errors=True)
 results=list(map(execute,selected)) if a.max_workers==1 else list(concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers).map(execute,selected));subprocess.run(['python3',str(ROOT/'experiments/v1_pre_exposure_prefix_audit.py')],cwd=ROOT,check=True);status=write_status(manifest);status['last_execution']={'selected':len(selected),'complete_or_resumed':sum(x in {'COMPLETE','RESUMED'} for x in results),'failed':sum(x=='FAILED' for x in results)};(RESULTS/'status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status,indent=2))
if __name__=='__main__':main()
