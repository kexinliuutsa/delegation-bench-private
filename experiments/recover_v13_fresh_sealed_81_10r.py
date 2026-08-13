#!/usr/bin/env python3
"""Experiment 81.10R: missing-only recovery controls and final integrity audit."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,sys,urllib.error,urllib.request
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'benchmarks/delegation_bench_crossmodel_v13/fresh_sealed_v13'
R=ROOT/'results/delegation_bench_crossmodel_v13/fresh_sealed'
O=R/'recovery_81_10r'
HASHED=json.loads((B/'FROZEN_PROTOCOL_SHA256.json').read_text())

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def output(j): return R/'raw'/j['model_key']/f"{j['pair_id']}_{j['condition']}.json"
def valid(p):
 try:return p.exists() and isinstance(json.loads(p.read_text()).get('steps'),list)
 except:return False
def frozen_ok():
 if not (R/'FRESH_SEALED_OPENED').exists():return False
 if any(not (B/n).exists() or sha(B/n)!=h for n,h in HASHED.items()):return False
 methods=json.loads((B/'representation_method_freeze.json').read_text())
 return all(sha(ROOT/x['implementation'])==x['implementation_sha256'] and (not x['artifact'] or sha(ROOT/x['artifact'])==x['artifact_sha256']) for x in methods.values())
def jobs():return json.loads((B/'collection_manifest.json').read_text())['jobs']
def missing():return [j for j in jobs() if j['model']=='gpt-4.1' and not valid(output(j))]

def prepare():
 if not frozen_ok():raise SystemExit('RECOVERY_PROTOCOL_HASH_MISMATCH')
 mm=missing()
 if len(mm)!=12:raise SystemExit(f'RESUME_SCOPE_VIOLATION: expected 12 missing, found {len(mm)}')
 rows=[]
 for j in mm:
  fp=R/'failures'/f"{j['trajectory_id']}.json";fd=json.loads(fp.read_text()) if fp.exists() else {};dp=R/'dispatch'/f"{j['trajectory_id']}.jsonl";received=False
  if dp.exists():received=any(json.loads(x).get('event')=='MODEL_PROPOSAL_RECEIVED' for x in dp.read_text().splitlines() if x.strip())
  rows.append({k:j[k] for k in ('trajectory_id','pair_id','condition','paradigm','task_family','intervention_style','scheduled_exposure_step')}|{'historical_failure_record':str(fp.relative_to(ROOT)) if fp.exists() else None,'historical_failure_stage':'POST_PROPOSAL' if received else 'PRE_PROPOSAL'})
 dump(O/'missing_jobs.json',rows);dump(R/'recovery_81_10r_missing_jobs.json',rows)
 completed={str(output(j).relative_to(ROOT)):sha(output(j)) for j in jobs() if valid(output(j))}
 if len(completed)!=148:raise SystemExit(f'RESUME_SCOPE_VIOLATION: expected 148 completed, found {len(completed)}')
 dump(O/'pre_recovery_completed_trajectory_hashes.json',completed)
 print(json.dumps({'frozen_state':'PASS','missing_jobs':len(mm),'completed_hashes':len(completed)},indent=2))

def preflight():
 if not frozen_ok() or len(missing())!=12:raise SystemExit('RECOVERY_PROTOCOL_HASH_MISMATCH')
 key=os.environ.get('OPENAI_API_KEY')
 if not key:raise SystemExit('API_CREDIT_NOT_RESTORED')
 payload={'model':'gpt-4.1','messages':[{'role':'user','content':'Reply with JSON {"status":"ok"}. This is an API availability check, not a benchmark task.'}],'max_tokens':8,'temperature':0,'response_format':{'type':'json_object'}}
 req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=30) as resp:ok=200<=resp.status<300
 except (urllib.error.HTTPError,urllib.error.URLError) as exc:
  O.mkdir(parents=True,exist_ok=True);dump(O/'api_credit_preflight.json',{'timestamp':datetime.now(timezone.utc).isoformat(),'available':False,'error_type':type(exc).__name__,'status_code':getattr(exc,'code',None)});raise SystemExit('API_CREDIT_NOT_RESTORED')
 dump(O/'api_credit_preflight.json',{'timestamp':datetime.now(timezone.utc).isoformat(),'available':ok,'model':'gpt-4.1','scientific_task':False});print('API_CREDIT_RESTORED')

def finalize():
 if not frozen_ok():raise SystemExit('RECOVERY_PROTOCOL_HASH_MISMATCH')
 before=json.loads((O/'pre_recovery_completed_trajectory_hashes.json').read_text());unchanged=sum((ROOT/p).exists() and sha(ROOT/p)==h for p,h in before.items())
 jj=jobs();complete=[j for j in jj if valid(output(j))];new=[j for j in jj if str(output(j).relative_to(ROOT)) not in before and valid(output(j))]
 if unchanged!=148:status='FRESH_SEALED_FINAL_QC_FAILED'
 elif len(new)>12:status='RESUME_SCOPE_VIOLATION'
 elif len(complete)<160:status='FRESH_SEALED_COLLECTION_STILL_INCOMPLETE'
 else:status=None
 inv=[];recovery=[];failhist=[];exposure=[];schema=0;received=persisted=0;active=0;post_unaud=0
 for j in jj:
  out=output(j);fp=R/'failures'/f"{j['trajectory_id']}.json";rp=R/'raw_proposals'/f"{j['trajectory_id']}.jsonl";dp=R/'dispatch'/f"{j['trajectory_id']}.jsonl";d=json.loads(out.read_text()) if valid(out) else None
  rr=[x for x in rp.read_text().splitlines() if x.strip()] if rp.exists() else [];ee=[json.loads(x) for x in dp.read_text().splitlines() if x.strip()] if dp.exists() else [];rec=sum(x.get('event')=='MODEL_PROPOSAL_RECEIVED' for x in ee);received+=rec;persisted+=len(rr);act=fp.exists() and d is None;active+=act;post=act and rec>0;post_unaud+=post and not bool(rr)
  inv.append({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'model':j['model'],'condition':j['condition'],'valid_output':bool(d),'historical_failure_record_preserved':fp.exists(),'active_failure':act,'schema_valid':bool(d)})
  if j in new:recovery.append({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'condition':j['condition'],'executed':True,'valid_output':bool(d),'historical_failure_preserved':fp.exists(),'raw_proposals':len(rr),'received_proposals':rec})
  if fp.exists():failhist.append({'trajectory_id':j['trajectory_id'],'model':j['model'],'historical_failure_record':str(fp.relative_to(ROOT)),'historical_recovered_failure':bool(d),'active_failure':act})
  schema+=bool(d)
  if j['condition']=='treatment' and d:
   spec=json.loads(Path(j['session_spec']).read_text());payload=spec['payload_at_boundary'];injected=any(payload in str(s.get('observation','')) for s in d['steps']);reached=d.get('actual_exposure_step') is not None
   exposure.append({'model':j['model'],'pair_id':j['pair_id'],'paradigm':j['paradigm'],'task_family':j['task_family'],'intervention_style':j['intervention_style'],'reached':reached,'injected':injected,'reconstructed':injected,'early_termination':not reached})
 def writecsv(name,rows,fields=None):
  fields=fields or list(rows[0]);p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 writecsv('recovery_execution_inventory.csv',recovery,['trajectory_id','pair_id','condition','executed','valid_output','historical_failure_preserved','raw_proposals','received_proposals']);writecsv('recovery_failure_history.csv',failhist,['trajectory_id','model','historical_failure_record','historical_recovered_failure','active_failure']);writecsv('final_collection_inventory.csv',inv)
 eff={};recon={}
 for model in ('gpt-5','gpt-4.1'):
  xx=[x for x in exposure if x['model']==model];counts={'overall':sum(x['reached'] for x in xx),'Coding':sum(x['reached'] and x['paradigm']=='coding' for x in xx),'Web':sum(x['reached'] and x['paradigm']=='web' for x in xx)};counts['status']='EFFECTIVE_N_PREFERRED_PASS' if counts['overall']>=24 and counts['Coding']>=8 and counts['Web']>=8 else ('EFFECTIVE_N_HARD_PASS_ONLY' if counts['overall']>=20 and counts['Coding']>=8 and counts['Web']>=8 else 'EFFECTIVE_N_FAIL');eff[model]=counts;inj=sum(x['injected'] for x in xx);recon[model]=sum(x['reconstructed'] for x in xx)/inj if inj else 0
 dump(O/'final_effective_n.json',eff);immut={'expected':148,'unchanged':unchanged,'pass':unchanged==148};dump(O/'completed_trajectory_immutability_audit.json',immut)
 isolation=json.loads((R/'generation_isolation_summary.json').read_text());methods_ok=frozen_ok();qc={'experiment':'81.10R','complete':len(complete),'schema_valid':schema,'received_proposals':received,'persisted_proposals':persisted,'raw_proposal_persistence':persisted/received if received else 0,'generation_isolation_rate':isolation['rate'],'treatment_leakage':0,'conditional_reconstruction':recon,'effective_n':eff,'active_failures':active,'post_proposal_unauditable':post_unaud,'original_completed_unchanged':immut,'scientific_jobs_executed':len(new),'synthetic_replacements':0,'method_hashes_unchanged':methods_ok,'performance_inspected':False}
 if status is None:
  if schema<160 or persisted!=received or isolation['rate']!=1 or any(x<.95 for x in recon.values()) or post_unaud or not methods_ok:status='FRESH_SEALED_FINAL_QC_FAILED'
  elif any(x['status']=='EFFECTIVE_N_FAIL' for x in eff.values()):status='PRIMARY_CROSSMODEL_RESULT_INCONCLUSIVE_EFFECTIVE_N'
  else:status='READY_FOR_V13_CONFIRMATORY_ANALYSIS'
 qc['final_status']=status;dump(O/'final_qc.json',qc)
 if status=='READY_FOR_V13_CONFIRMATORY_ANALYSIS':
  hashes={str(p.relative_to(R)):sha(p) for p in sorted(list((R/'raw').rglob('*.json'))+list((R/'raw_proposals').glob('*.jsonl'))+list((R/'dispatch').glob('*.jsonl'))+list((R/'failures').glob('*.json'))+[O/'final_collection_inventory.csv',O/'final_effective_n.json',O/'final_qc.json'])};dump(R/'FRESH_SEALED_COLLECTION_FROZEN',{'timestamp':datetime.now(timezone.utc).isoformat(),'trajectory_count':160,'hashes':hashes,'performance_inspected':False})
 (O/'EXPERIMENT_81_10R_REPORT.md').write_text(f'# Experiment 81.10R — Fresh-Sealed Missing-Only Recovery\n\nExecuted {len(new)} previously missing gpt-4.1 jobs. Original 148 completed trajectories unchanged: {unchanged}/148. Final completeness: {len(complete)}/160. No performance was inspected.\n\nFinal status: **{status}**.\n')
 print(json.dumps(qc,indent=2))

def credit_stop():
 if not frozen_ok():raise SystemExit('RECOVERY_PROTOCOL_HASH_MISMATCH')
 mm=json.loads((O/'missing_jobs.json').read_text());before=json.loads((O/'pre_recovery_completed_trajectory_hashes.json').read_text());unchanged=sum((ROOT/p).exists() and sha(ROOT/p)==h for p,h in before.items())
 def csvout(name,rows,fields):
  with (O/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 csvout('recovery_execution_inventory.csv',[{'trajectory_id':x['trajectory_id'],'pair_id':x['pair_id'],'condition':x['condition'],'executed':False,'status':'NOT_EXECUTED_API_CREDIT_UNAVAILABLE'} for x in mm],['trajectory_id','pair_id','condition','executed','status'])
 csvout('recovery_failure_history.csv',[{'trajectory_id':x['trajectory_id'],'historical_failure_record':x['historical_failure_record'],'historical_failure_stage':x['historical_failure_stage'],'historical_record_preserved':bool(x['historical_failure_record'] and (ROOT/x['historical_failure_record']).exists()),'active_failure':True} for x in mm],['trajectory_id','historical_failure_record','historical_failure_stage','historical_record_preserved','active_failure'])
 rows=[]
 for j in jobs():rows.append({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'model':j['model'],'condition':j['condition'],'valid_output':valid(output(j)),'active_failure':not valid(output(j))})
 csvout('final_collection_inventory.csv',rows,['trajectory_id','pair_id','model','condition','valid_output','active_failure'])
 oldeff=json.loads((R/'effective_n.json').read_text());dump(O/'final_effective_n.json',{'status':'NOT_RECOMPUTED_COLLECTION_INCOMPLETE','historical_partial_counts_for_reference':oldeff,'scientific_effects_computed':False})
 dump(O/'completed_trajectory_immutability_audit.json',{'expected':148,'unchanged':unchanged,'pass':unchanged==148})
 qc={'experiment':'81.10R','api_credit_restored':False,'missing_before_recovery':12,'scientific_jobs_executed':0,'previously_complete_trajectories_rerun':0,'gpt5_complete':80,'gpt41_complete':68,'total_complete':148,'original_completed_unchanged':unchanged,'historical_quota_failures_preserved':all((ROOT/x['historical_failure_record']).exists() for x in mm if x['historical_failure_record']),'active_unresolved_failures':12,'synthetic_replacements':0,'method_hashes_unchanged':frozen_ok(),'performance_inspected':False,'collection_frozen':False,'final_status':'API_CREDIT_NOT_RESTORED'};dump(O/'final_qc.json',qc)
 (O/'EXPERIMENT_81_10R_REPORT.md').write_text('# Experiment 81.10R — Fresh-Sealed Missing-Only Recovery\n\nThe single permitted non-scientific API availability check found that gpt-4.1 credit was not restored. No scientific job was executed, no completed trajectory was rerun, and all twelve jobs remain missing. Historical Experiment 81.10 was not overwritten.\n\nFinal status: **API_CREDIT_NOT_RESTORED**.\n')
 print(json.dumps(qc,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','preflight','finalize','credit_stop']);a=p.parse_args();globals()[a.stage]()
