#!/usr/bin/env python3
"""Experiment 81.6 read-only evidence/reproducibility audit."""
from __future__ import annotations
import csv,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'results/delegation_bench_crossmodel_v12/expanded_smoke';OUT=ROOT/'results/delegation_bench_crossmodel_v12/action_execution_audit';V1=ROOT/'results/delegation_bench_crossmodel_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,rows,fields):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 failures=sorted(E.glob('*model_b_treatment.failure.txt'));assert len(failures)==5
 historical=[E/'smoke_manifest.json',E/'frozen_runtime_hashes.json',E/'trajectory_inventory.csv',E/'qc_summary.json',ROOT/'runners/v1_agent_common.py']+failures+sorted((E/'raw').rglob('*.json'))
 evidence={'experiment':'81.6','recorded_before_audit_outputs':True,'experiment_81_5_status':'MEASUREMENT_INFRASTRUCTURE_FAILURE','manifest_sha256':sha(E/'smoke_manifest.json'),'frozen_runner_sha256':sha(ROOT/'runners/v1_agent_common.py'),'trajectory_inventory_sha256':sha(E/'trajectory_inventory.csv'),'qc_summary_sha256':sha(E/'qc_summary.json'),'failed_raw_proposal_files':[],'failed_raw_proposals_persisted':0,'error_record_hashes':{p.name:sha(p) for p in failures},'successful_trajectory_hashes':{str(p.relative_to(ROOT)):sha(p) for p in sorted((E/'raw').rglob('*.json'))},'all_historical_hashes':{str(p.relative_to(ROOT)):sha(p) for p in historical}}
 (OUT/'historical_hashes.json').write_text(json.dumps(evidence,indent=2)+'\n')
 manifest=json.loads((E/'smoke_manifest.json').read_text());forensics=[]
 for f in failures:
  tid=f.name.removesuffix('.failure.txt');job=next(j for j in manifest['jobs'] if j['trajectory_id']==tid);err=f.read_text();match=re.search(r"FileNotFoundError:.*?'([^']+)'",err,re.S);derived=match.group(1) if match else ''
  forensics.append({'pair_id':job['pair_id'],'task_family':job['task_family'],'trajectory_role':'treatment','raw_proposal':'UNAVAILABLE','tool_name':'UNAVAILABLE','raw_arguments':'UNAVAILABLE','runner_parsed_tool':'read_file (inferred from stack frame; not raw evidence)','runner_parsed_path':derived,'notice_or_control_token_if_present':'UNAVAILABLE_IN_RAW_FORM','exception':'FileNotFoundError','execution_attempted':'YES','filesystem_access_attempted':'YES','classification':'INSUFFICIENT_RAW_EVIDENCE','evidence_note':'exception preserves derived path and read_file stack branch, but no pre-dispatch proposal payload was persisted'})
 fields=list(forensics[0]);write(OUT/'failed_action_forensics.csv',forensics,fields)
 # Corpus is frozen for audit completeness, but failed cases explicitly contain no
 # proposal and thus cannot authorize parser/dispatch replay or repair.
 corpus=[]
 for r in forensics:corpus.append({'case_id':r['pair_id']+'_failed','model':'gpt-4.1','historical_outcome':'FAILED','raw_proposal_available':False,'raw_proposal':None,'source':'failure stderr only','eligible_for_dispatch_replay':False})
 for p in sorted((E/'raw').rglob('*.json')):
  d=json.loads(p.read_text());model=d['model']
  for s in d.get('steps',[]):
   # Persisted successful trajectory stores tool plus JSON-serialized arguments,
   # not the exact pre-dispatch API payload. Retain it as an archived dispatch
   # record and do not mislabel it as verbatim raw proposal.
   corpus.append({'case_id':str(p.relative_to(E))+f":step{s['step']}",'model':model,'historical_outcome':'SUCCESS','raw_proposal_available':False,'raw_proposal':None,'persisted_tool':s.get('tool'),'persisted_arguments':s.get('arguments'),'source':'post-dispatch trajectory step','eligible_for_dispatch_replay':False})
 corpus_obj={'frozen_before_any_repair':True,'sha_scope_note':'SHA below covers cases only','cases':corpus};corpus_obj['cases_sha256']=hashlib.sha256(json.dumps(corpus,sort_keys=True,separators=(',',':')).encode()).hexdigest();(OUT/'runner_regression_corpus.json').write_text(json.dumps(corpus_obj,indent=2)+'\n')
 reproduction={'failed_cases':5,'raw_failed_proposals_available':0,'historical_failures_reproduced':0,'historical_failure_reproduction_rate':0.0,'offline_replay_attempted':False,'reason':'No failed pre-dispatch proposal payloads were persisted. Exception-derived paths cannot reconstruct tool identity, original argument schema, or action/message ambiguity without inference.','stop_status':'FAILURE_NOT_REPRODUCIBLE_FROM_ARCHIVED_EVIDENCE'};(OUT/'failure_reproduction.json').write_text(json.dumps(reproduction,indent=2)+'\n')
 dispatch_fields=['case_id','old_dispatch','new_dispatch','behavior_change','evaluation_status'];dispatch_rows=[{'case_id':r['pair_id'],'old_dispatch':'NOT_REPLAYABLE','new_dispatch':'NO_NEW_RUNNER','behavior_change':'NA','evaluation_status':'INSUFFICIENT_RAW_EVIDENCE'} for r in forensics];write(OUT/'old_vs_new_dispatch.csv',dispatch_rows,dispatch_fields)
 compat=[]
 for model in ('gpt-5','gpt-4.1'):
  persisted=[x for x in corpus if x['model']==model];compat.append({'model':model,'persisted_post_dispatch_steps':sum(x['historical_outcome']=='SUCCESS' for x in persisted),'verbatim_raw_proposals_available':0,'parse_success':'NOT_EVALUATED','valid_action_dispatch':'NOT_EVALUATED','notice_message_recognition':'NOT_EVALUATED','unresolved_rate':'NOT_EVALUATED','semantic_changes_to_successful_dispatch':0,'reason':'no repaired interpretation layer authorized'})
 write(OUT/'crossmodel_offline_compatibility.csv',compat,list(compat[0]))
 invariance={'scientific_logic_changed':False,'intervention_assignment_changed':False,'intervention_payload_changed':False,'exposure_schedule_changed':False,'task_fixtures_changed':False,'pair_construction_changed':False,'prompts_changed':False,'generation_isolation_logic_changed':False,'representation_extraction_changed':False,'raw_coral_mmd_pidr_changed':False,'downstream_metrics_changed':False,'success_gates_changed':False,'model_b_changed':False,'runner_created':False,'historical_trajectories_retried':False,'model_calls':0,'performance_inspected':False,'fresh_sealed_opened':False};(OUT/'scientific_invariance_audit.json').write_text(json.dumps(invariance,indent=2)+'\n')
 status='FAILURE_NOT_REPRODUCIBLE_FROM_ARCHIVED_EVIDENCE'
 (OUT/'EXPERIMENT_81_6_REPORT.md').write_text(f'''# Experiment 81.6 — Cross-Model Action-Execution Robustness Audit\n\nExperiment 81.5 remains permanently **MEASUREMENT_INFRASTRUCTURE_FAILURE**. Its five jobs were not retried. No model call or fresh-sealed access occurred.\n\nAll five error records show a `read_file` stack branch and a derived nonexistent path, but Experiment 81.5 persisted neither the failed API proposal nor a pre-dispatch event log. Accordingly, the original tool field, raw argument layout, and any competing notice/message interpretation are unavailable. The audit prohibition on inference requires all five classifications to be **INSUFFICIENT_RAW_EVIDENCE**.\n\nThe archived successful trajectories likewise contain post-dispatch tool/argument records, not verbatim pre-dispatch proposals. They were frozen into the regression corpus for provenance, but cannot substitute for the missing five failed proposals. Historical failure reproduction is 0/5 because replay was impossible—not because the failures did not happen.\n\nWithout reproducible inputs, no deterministic dispatch defect can be validated and no runner patch is authorized. No v1.3 runner, tests, contract, or compatibility-preflight plan was created. Future infrastructure work must first add append-only pre-dispatch raw proposal persistence in a separately versioned diagnostic protocol.\n\nFinal status: **{status}**.\n''')
 # historical files remain unchanged
 assert {str(p.relative_to(ROOT)):sha(p) for p in historical}==evidence['all_historical_hashes']
 assert not (V1/'FRESH_SEALED_OPENED').exists() and json.loads((V1/'SEALED_STATUS.json').read_text())['fresh_sealed_opened'] is False
 print(json.dumps({'classifications':{'INSUFFICIENT_RAW_EVIDENCE':5},'reproduced':'0/5','new_runner_created':False,'status':status},indent=2))
if __name__=='__main__':main()
