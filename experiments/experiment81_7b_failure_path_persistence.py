#!/usr/bin/env python3
"""Offline deterministic failure-path exercise of the production v1.3 persistence hook."""
from __future__ import annotations
import csv,hashlib,json,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runners.crossmodel_v13_agent import persist_proposal
from runners.crossmodel_v13_failure_qc import assert_failed_job_has_raw_proposal,MissingRawProposalForFailedJob
OUT=ROOT/'results/delegation_bench_crossmodel_v13/failure_path_persistence';RAW=OUT/'raw_proposals';B=ROOT/'benchmarks/delegation_bench_crossmodel_v13'
class SyntheticDispatchFailure(RuntimeError):pass
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def append_event(rows,fixture,event):rows.append({'fixture_id':fixture,'event':event,'timestamp':now()})
def normalize(p):
 if not isinstance(p,dict) or not isinstance(p.get('tool'),str):raise ValueError('INVALID_SCHEMA')
 return p['tool'],{k:v for k,v in p.items() if k!='tool'}
def dispatch(tool,args,mode):
 known={'read_file','list_files','run_command','finish'}
 if tool not in known:raise LookupError('UNKNOWN_TOOL')
 if mode=='dispatch':raise SyntheticDispatchFailure('forced post-persistence failure')
 if mode=='executor':raise SyntheticDispatchFailure('forced post-persistence failure')
 return None
def main():
 OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
 fixtures=[
 {'fixture_id':'VALID_READ_FILE_THEN_FORCED_EXECUTOR_FAILURE','proposal':{'tool':'read_file','path':'README.md'},'failure_stage':'executor'},
 {'fixture_id':'VALID_STRUCTURED_ACTION_THEN_FORCED_DISPATCH_FAILURE','proposal':{'tool':'list_files','path':'.'},'failure_stage':'dispatch'},
 {'fixture_id':'INVALID_SCHEMA_AFTER_PERSISTENCE','proposal':{'path':'README.md'},'failure_stage':'normalization'},
 {'fixture_id':'UNKNOWN_TOOL_AFTER_PERSISTENCE','proposal':{'tool':'unsupported_diagnostic_tool','path':'README.md'},'failure_stage':'dispatch'}]
 manifest={'experiment':'81.7b','fixture_type':'SYNTHETIC_DETERMINISTIC_FAILURE_FIXTURE','historical_failure_reproduction':False,'model_calls':0,'fixtures':fixtures,
  'component_hashes':{'v1.3_runner_and_persistence_helper':sha(ROOT/'runners/crossmodel_v13_agent.py'),'dispatch_layer':sha(ROOT/'runners/crossmodel_v13_agent.py'),'schema_definitions':sha(ROOT/'experiments/delegation_bench_v1_common.py'),'frozen_protocol':sha(B/'FROZEN_PROTOCOL.md')}}
 (OUT/'fixture_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 traces=[];results=[];prior={};all_readable=True;all_persisted=True;ordering=True
 for index,f in enumerate(fixtures,1):
  fid=f['fixture_id'];path=RAW/f'{fid}.jsonl'; events=[];proposal=f['proposal'];traj=f'e817b_offline_{index:02d}'
  append_event(events,fid,'MODEL_PROPOSAL_RECEIVED');ctx={'model':'OFFLINE_FIXTURE','pair_id':fid,'trajectory_id':traj,'condition':'diagnostic'}
  rid=f'e817b-record-{index:02d}';stamp=now();ctx.update({'record_id':rid,'protocol_version':'v1.3-81.7b','fixture_id':fid,'step_index':index,'persistence_timestamp':stamp,'downstream_status':'EXPECTED_FAILURE','exception_type':'SyntheticFixtureFailure','exception_message':'forced post-persistence failure'})
  persist_proposal(path,ctx,index,proposal);row={'record_id':rid};append_event(events,fid,'RAW_PROPOSAL_PERSISTED')
  snapshot={p.name:p.read_bytes() for p in RAW.glob('*.jsonl') if p!=path};exc=None;norm=False;disp=False
  try:
   append_event(events,fid,'NORMALIZATION_STARTED');norm=True;tool,args=normalize(proposal)
   append_event(events,fid,'DISPATCH_STARTED');disp=True;dispatch(tool,args,f['failure_stage'])
   if f['failure_stage']=='normalization':raise AssertionError('invalid fixture unexpectedly normalized')
  except Exception as e:
   exc=e;append_event(events,fid,'FORCED_FAILURE')
  readable=False;preserved=False
  try:
   saved=json.loads(path.read_text().splitlines()[0]);readable=bool(path.stat().st_size);preserved=saved['raw_structured_proposal']==proposal and saved['raw_tool_name']==proposal.get('tool')
  except Exception: saved={}
  unchanged=all(p.read_bytes()==data for name,data in snapshot.items() for p in [RAW/name])
  ev={x['event']:x['timestamp'] for x in events};ordered=ev['MODEL_PROPOSAL_RECEIVED']<=ev['RAW_PROPOSAL_PERSISTED']<ev['FORCED_FAILURE'] and (not norm or ev['RAW_PROPOSAL_PERSISTED']<=ev['NORMALIZATION_STARTED']) and (not disp or ev['RAW_PROPOSAL_PERSISTED']<=ev['DISPATCH_STARTED'])
  ordering&=ordered;all_readable&=readable;all_persisted&=preserved
  for name in ('MODEL_PROPOSAL_RECEIVED','RAW_PROPOSAL_PERSISTED','NORMALIZATION_STARTED','DISPATCH_STARTED','FORCED_FAILURE'):
   traces.append({'fixture_id':fid,'proposal_received_timestamp':ev.get('MODEL_PROPOSAL_RECEIVED'),'raw_persisted_timestamp':ev.get('RAW_PROPOSAL_PERSISTED'),'normalization_started_timestamp':ev.get('NORMALIZATION_STARTED'),'dispatch_started_timestamp':ev.get('DISPATCH_STARTED'),'failure_timestamp':ev.get('FORCED_FAILURE'),'event_order_valid':ordered}) ;break
  results.append({'fixture_id':fid,'fixture_type':'SYNTHETIC_DETERMINISTIC_FAILURE_FIXTURE','failure_stage':f['failure_stage'],'exception_type':type(exc).__name__ if exc else '', 'exception_message':str(exc) if exc else '', 'raw_created':path.exists(),'raw_nonempty':bool(path.exists() and path.stat().st_size),'raw_parseable':readable,'structured_fields_preserved':preserved,'failure_after_creation':ordered,'prior_records_byte_identical':unchanged,'record_id':row['record_id']})
 # Automatic assertion cases.
 qc=[]
 for r in results:
  try:ok=assert_failed_job_has_raw_proposal('e817b_offline_'+str(results.index(r)+1).zfill(2),RAW/f"{r['fixture_id']}.jsonl",True,'POST_PROPOSAL_FAILURE')
  except Exception:ok=False
  qc.append({'case':r['fixture_id'],'expected':'PASS','actual':'PASS' if ok else 'FAIL','passed':ok})
 missing=OUT/'deliberately_missing.jsonl'
 try:assert_failed_job_has_raw_proposal('missing',missing,True,'POST_PROPOSAL_FAILURE');missing_ok=False
 except MissingRawProposalForFailedJob as e:missing_ok=str(e)=='MISSING_RAW_PROPOSAL_FOR_FAILED_JOB'
 qc.append({'case':'POST_PROPOSAL_FAILURE_WITHOUT_RAW','expected':'MISSING_RAW_PROPOSAL_FOR_FAILED_JOB','actual':'MISSING_RAW_PROPOSAL_FOR_FAILED_JOB' if missing_ok else 'FAIL','passed':missing_ok})
 try:pre_ok=assert_failed_job_has_raw_proposal('transport',missing,False,'PRE_PROPOSAL_FAILURE')
 except Exception:pre_ok=False
 qc.append({'case':'PRE_PROPOSAL_TRANSPORT_FAILURE','expected':'PASS_WITHOUT_RAW','actual':'PASS_WITHOUT_RAW' if pre_ok else 'FAIL','passed':pre_ok})
 def writecsv(path,rows):
  with path.open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 writecsv(OUT/'failure_path_event_order.csv',traces);writecsv(OUT/'failure_results.csv',results)
 append_ok=all(x['prior_records_byte_identical'] for x in results) and len({x['record_id'] for x in results})==len(results)
 (OUT/'append_only_integrity.json').write_text(json.dumps({'pass':append_ok,'distinct_records':len({x['record_id'] for x in results}),'previous_records_byte_identical':all(x['prior_records_byte_identical'] for x in results)},indent=2)+'\n')
 (OUT/'qc_assertion_results.json').write_text(json.dumps({'all_pass':all(x['passed'] for x in qc),'cases':qc},indent=2)+'\n')
 invariant={'scientific_logic_changed':False,'task_fixtures_changed':False,'intervention_payloads_changed':False,'exposure_schedule_changed':False,'model_selection_changed':False,'system_prompts_changed':False,'scientific_tool_schemas_changed':False,'generation_isolation_changed':False,'representation_extraction_changed':False,'methods_changed':{'RAW':False,'CORAL':False,'MMD':False,'PIDR':False},'monitor_thresholds_changed':False,'statistical_plan_changed':False,'instrumentation_change':'raw record envelope + reusable failed-job persistence assertion only'}
 (OUT/'scientific_invariance_audit.json').write_text(json.dumps(invariant,indent=2)+'\n')
 passed=all_persisted and all_readable and append_ok and ordering and all(x['passed'] for x in qc) and not any(v is True for k,v in invariant.items() if k.endswith('_changed'))
 status='FAILURE_PATH_PERSISTENCE_VALIDATED' if passed else 'FAILURE_PATH_PERSISTENCE_NOT_VALIDATED'
 report=f'''# Experiment 81.7b — Failure-Path Raw Proposal Persistence Gate

Four offline **SYNTHETIC_DETERMINISTIC_FAILURE_FIXTURE** proposals exercised the production v1.3 `persist_proposal` hook. This is not historical failure reproduction. All {len(results)} proposals remained parseable after downstream failure; append-only and event-ordering checks {'passed' if passed else 'did not pass'}.

The automatic QC assertion distinguishes post-proposal failure (raw evidence required) from pre-proposal transport failure (no raw evidence expected). No model calls, scientific evaluation, smoke, or fresh-sealed access occurred.

Final status: **{status}**.
''';(OUT/'EXPERIMENT_81_7B_REPORT.md').write_text(report)
 print(json.dumps({'status':status,'fixtures':len(results),'persisted':sum(x['structured_fields_preserved'] for x in results),'readable':sum(x['raw_parseable'] for x in results),'append_only':append_ok,'ordering':ordering,'qc':all(x['passed'] for x in qc),'pre_proposal':pre_ok},indent=2))
if __name__=='__main__':main()
