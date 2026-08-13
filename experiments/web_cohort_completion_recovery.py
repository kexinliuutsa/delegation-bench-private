#!/usr/bin/env python3
"""Experiment 69: bounded recovery for incomplete frozen-v1 Web trajectories."""
from __future__ import annotations
import argparse,csv,json,shlex,shutil,subprocess,tempfile,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from delegation_bench_v1_common import ROOT,BENCH,RESULTS

ATTEMPT_COLUMNS=['pair_id','trajectory_id','task_family','intervention_style','seed','attempt','start_time','end_time','result','failure_type','stderr_path','protocol_hash_verified']
def now():return datetime.now(timezone.utc).isoformat()
def valid(path,job):
 try:value=json.loads(path.read_text())
 except Exception:return False
 return value.get('task')==job['task'] and value.get('seed')==job['seed'] and value.get('model')==job['agent_model'] and isinstance(value.get('steps'),list) and bool(value['steps'])
def existing_attempts(path):
 if not path.exists():return []
 return list(csv.DictReader(path.open()))
def write_attempts(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as handle:
  writer=csv.DictWriter(handle,fieldnames=ATTEMPT_COLUMNS);writer.writeheader();writer.writerows(rows)
def verify_protocol():
 done=subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,capture_output=True,text=True)
 if done.returncode:raise RuntimeError(done.stderr or done.stdout)
 return True
def attempt(job,number):
 verify_protocol();destination=RESULTS/'raw'/f"{job['pair_id']}_{job['condition']}.json";failure=RESULTS/'audits'/f"{job['trajectory_id']}.recovery_attempt_{number}.stderr.txt"
 if destination.exists() and not valid(destination,job):destination.unlink()
 if failure.exists():failure.unlink()
 work=Path(tempfile.mkdtemp(prefix=f"recovery_{job['trajectory_id']}_",dir=RESULTS/'manifests'));environment=work/'environment';native=work/'native.json';shutil.copytree(job['initial_environment_path'],environment);runner=ROOT/job['runner'];start=now();result='FAILED';failure_type=''
 command=f"python3 {shlex.quote(str(runner))} --task {shlex.quote(job['task'])} --environment {shlex.quote(str(environment))} --session-spec {shlex.quote(job['session_spec'])} --seed {job['seed']} --model {shlex.quote(job['agent_model'])} --output {shlex.quote(str(native))} --max-steps {job['max_steps']}"
 try:
  done=subprocess.run(command,shell=True,cwd=ROOT,text=True,capture_output=True,timeout=job['timeout_seconds']+30)
  if done.returncode:raise RuntimeError(done.stderr[-4000:] or f'exit {done.returncode}')
  if not native.exists():raise RuntimeError('runner produced no trajectory')
  destination.write_text(native.read_text())
  if not valid(destination,job):destination.unlink(missing_ok=True);raise RuntimeError('runner output failed trajectory validation')
  result='RECOVERED'
 except subprocess.TimeoutExpired as exc:
  failure_type='TIMEOUT';failure.write_text(f'{type(exc).__name__}: {exc}\n')
 except Exception as exc:
  failure_type=type(exc).__name__.upper();failure.write_text(f'{type(exc).__name__}: {exc}\n')
 finally:shutil.rmtree(work,ignore_errors=True)
 return {'pair_id':job['pair_id'],'trajectory_id':job['trajectory_id'],'task_family':job['task_family'],'intervention_style':job['intervention_style'],'seed':job['seed'],'attempt':number,'start_time':start,'end_time':now(),'result':result,'failure_type':failure_type,'stderr_path':str(failure.relative_to(ROOT)) if failure.exists() else '','protocol_hash_verified':True}
def missingness(manifest,missing,attempt_rows,path):
 planned=[j for j in manifest['jobs'] if j['paradigm']=='web'];planned_pairs={j['pair_id'] for j in planned};failed_by_id={j['trajectory_id']:j for j in missing};counts=Counter(r['trajectory_id'] for r in attempt_rows);rows=[]
 dimensions=('task_family','intervention_style','scheduled_exposure_step')
 for job in missing:
  control=RESULTS/'raw'/f"{job['pair_id']}_control.json";raw=json.loads(control.read_text()) if control.exists() else {};last=next((r for r in reversed(attempt_rows) if r['trajectory_id']==job['trajectory_id']),{})
  row={'row_type':'RECOVERY_TRAJECTORY','pair_id':job['pair_id'],'trajectory_id':job['trajectory_id'],'task_family':job['task_family'],'intervention_style':job['intervention_style'],'seed':job['seed'],'scheduled_exposure_step':job['scheduled_exposure_step'],'control_trajectory_length':len(raw.get('steps',[])) if raw else 'UNKNOWN','control_completion_status':'EARLY_TERMINATION' if raw.get('early_termination') else ('COMPLETE' if raw.get('finished') else ('INCOMPLETE' if raw else 'MISSING')),'failure_type':last.get('failure_type') or last.get('result','UNKNOWN'),'number_of_attempts':counts[job['trajectory_id']],'category':'','planned_web_pairs':'','failed_trajectories':'','failure_rate':''};rows.append(row)
 for dim in dimensions:
  full=Counter(next(j for j in planned if j['pair_id']==pid)[dim] for pid in planned_pairs);fail=Counter(j[dim] for j in missing)
  for category,total in sorted(full.items(),key=lambda x:str(x[0])):rows.append({'row_type':f'CONCENTRATION_BY_{dim.upper()}','pair_id':'','trajectory_id':'','task_family':'','intervention_style':'','seed':'','scheduled_exposure_step':'','control_trajectory_length':'','control_completion_status':'','failure_type':'','number_of_attempts':'','category':category,'planned_web_pairs':total,'failed_trajectories':fail[category],'failure_rate':round(fail[category]/total,6)})
 fields=['row_type','pair_id','trajectory_id','task_family','intervention_style','seed','scheduled_exposure_step','control_trajectory_length','control_completion_status','failure_type','number_of_attempts','category','planned_web_pairs','failed_trajectories','failure_rate'];path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as handle:writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--max-attempts',type=int,default=3);a=p.parse_args()
 if a.max_attempts!=3:raise SystemExit('Experiment 69 requires exactly 3 maximum additional attempts')
 verify_protocol();manifest=json.loads((BENCH/'collection_manifest.json').read_text());raw=RESULTS/'raw';missing_before=[j for j in manifest['jobs'] if j['paradigm']=='web' and not (raw/f"{j['pair_id']}_{j['condition']}.json").exists()]
 if any(j['condition']!='treatment' for j in missing_before):raise SystemExit('recovery scope contains a non-treatment trajectory')
 attempts_path=RESULTS/'audits/web_recovery_attempts.csv';rows=existing_attempts(attempts_path);prior=Counter(r['trajectory_id'] for r in rows)
 if a.execute:
  for job in missing_before:
   for number in range(prior[job['trajectory_id']]+1,4):
    row=attempt(job,number);rows.append(row);write_attempts(attempts_path,rows)
    if row['result']=='RECOVERED':break
 missing_after=[j for j in manifest['jobs'] if j['paradigm']=='web' and not (raw/f"{j['pair_id']}_{j['condition']}.json").exists()];recovery_ids={r['trajectory_id'] for r in rows};recovery_cohort=[j for j in manifest['jobs'] if j['trajectory_id'] in recovery_ids];missingness(manifest,recovery_cohort,rows,RESULTS/'audits/web_missingness_analysis.csv')
 for script in ('v1_generation_isolation_audit.py','v1_pre_exposure_prefix_audit.py','normalize_delegation_bench_v1.py','delegation_bench_v1_measurements.py'):
  subprocess.run(['python3',str(ROOT/'experiments'/script)],cwd=ROOT,check=True)
 complete_pairs=sum(all((raw/f'{pid}_{role}.json').exists() for role in ('control','treatment')) for pid in {j['pair_id'] for j in manifest['jobs'] if j['paradigm']=='web'})
 recovered=len(missing_before)-len(missing_after);status=json.loads((RESULTS/'status.json').read_text()) if (RESULTS/'status.json').exists() else {};pre_summary=json.loads((RESULTS/'audits/pre_exposure_prefix_audit.summary.json').read_text());completed_trajectories=sum((raw/f"{j['pair_id']}_{j['condition']}.json").exists() for j in manifest['jobs']);total_pairs=80+complete_pairs;status.update({'completed_pairs':total_pairs,'completed_trajectories':completed_trajectories,'coding_pairs':80,'web_pairs':complete_pairs,'pre_exposure_valid_pairs':pre_summary.get('trajectory_level_valid_pairs',0),'temporal_onset_valid_pairs':pre_summary.get('temporal_onset_valid_pairs',0),'web_recovery':{'missing_trajectories_before_recovery':len(missing_before),'recovered':recovered,'persistent_failures':len(missing_after)},'collection_status':'COMPLETE' if complete_pairs==80 else 'COMPLETE_WITH_PERSISTENT_MISSINGNESS','benchmark_ready':complete_pairs==80});(RESULTS/'status.json').write_text(json.dumps(status,indent=2)+'\n')
 if a.execute and missing_after:
  for job in missing_after:(RESULTS/'audits'/f"{job['trajectory_id']}.PERSISTENT_COLLECTION_FAILURE").write_text(f'pair_id={job["pair_id"]}\nattempts={sum(r["trajectory_id"]==job["trajectory_id"] for r in rows)}\n')
 print(json.dumps({'missing_trajectories_before_recovery':len(missing_before),'recovered':recovered,'persistent_failures':len(missing_after),'complete_web_pairs':complete_pairs,'total_complete_benchmark_pairs':80+complete_pairs,'benchmark_ready':complete_pairs==80},indent=2))
if __name__=='__main__':main()
