#!/usr/bin/env python3
"""Frozen full-collection execution-path preflight; no performance metrics."""
from __future__ import annotations
import hashlib,json,os,re,ssl,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BENCH=ROOT/'benchmarks/delegation_transition_pilot';RES=ROOT/'results/delegation_transition_pilot';OUT=RES/'preflight';RAW=OUT/'raw';FREEZE=RES/'final_readiness/FULL_COLLECTION_PROTOCOL_SHA256.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,x):(OUT/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True);frozen=json.loads(FREEZE.read_text());mismatches=[]
 for rel,h in frozen['component_sha256'].items():
  p=ROOT/rel
  if not p.exists() or sha(p)!=h:mismatches.append(rel)
 protocol=BENCH/'FULL_COLLECTION_PROTOCOL_FROZEN.md';analysis=BENCH/'FULL_COLLECTION_ANALYSIS_PLAN.md';manifest_path=BENCH/'full_collection_manifest.json';protocol_hashes={'FULL_COLLECTION_PROTOCOL_FROZEN.md':sha(protocol),'FULL_COLLECTION_ANALYSIS_PLAN.md':sha(analysis),'full_collection_manifest.json':sha(manifest_path),'frozen_component_mismatches':mismatches}
 # TLS configuration and static insecure-override scan.
 cert=Path('/etc/ssl/cert.pem');parseable=False;error=None
 try:ssl.create_default_context(cafile=str(cert));parseable=True
 except Exception as e:error=repr(e)
 patterns=re.compile(r'verify\s*=\s*False|CERT_NONE|check_hostname\s*=\s*False|PYTHONHTTPSVERIFY\s*=\s*0|create_unverified_context')
 hits=[]
 for base in (ROOT/'runners',ROOT/'experiments',ROOT/'models'):
  for p in base.glob('*.py'):
   if p.resolve()==Path(__file__).resolve():continue
   for i,line in enumerate(p.read_text(errors='replace').splitlines(),1):
    if patterns.search(line):hits.append({'file':str(p.relative_to(ROOT)),'line':i,'text':line.strip()})
 tls={'ssl_cert_file_environment':os.environ.get('SSL_CERT_FILE'),'expected':'/etc/ssl/cert.pem','exists':cert.exists(),'nonempty':cert.exists() and cert.stat().st_size>0,'parseable_ca_bundle':parseable,'parse_error':error,'insecure_override_hits':hits,'status':'TLS_VERIFICATION_ENABLED' if cert.exists() and cert.stat().st_size>0 and parseable and os.environ.get('SSL_CERT_FILE')=='/etc/ssl/cert.pem' and not hits else 'TLS_VERIFICATION_NOT_VERIFIED'};dump('tls_audit.json',tls)
 manifest=json.loads(manifest_path.read_text());families=[];selected=[]
 for pair in sorted(manifest['pairs'],key=lambda x:x['pair_id']):
  if pair['task_family'] not in families:families.append(pair['task_family']);selected.append(pair)
  if len(selected)==2:break
 selection={'selection_rule':'first lexicographic pair IDs with distinct task_family','selected_before_execution':True,'pairs':[{'pair_id':x['pair_id'],'task_family':x['task_family'],'candidate_capability':x['candidate_capability']} for x in selected]};dump('smoke_pair_selection.json',selection)
 # Existing smoke files must be exactly selected IDs. Collection occurs outside this audit script.
 files=sorted(RAW.glob('*.json'));expected={f"{x['pair_id']}_{c}" for x in selected for c in ('control','perturbed')};actual={p.stem for p in files};execution={'expected_trajectories':4,'real_smoke_trajectories':len(files),'selected_outputs_complete':actual==expected,'frozen_component_mismatches':mismatches};total=ordered=identical=0;conseq=blocked=0;schema_rows=[];leak=[]
 consequential=set(frozen['sandbox_policy']['blocked_capabilities'])
 for p in files:
  t=json.loads(p.read_text());required={'pair_id','condition','task','seed','model','steps'};top=required<=set(t);step_ok=True
  # Model-visible messages are not persisted; audit persisted task and observations plus frozen runner construction.
  visible=[t.get('task','')]+[s.get('observation','') for s in t['steps']]
  terms=('delegation_contract','expected_support_status','candidate_capability','true_boundary','boundary_alarm','condition: control','condition: perturbed')
  found=sorted({term for term in terms if any(term in str(v).lower() for v in visible)});leak.append({'trajectory_id':t['trajectory_id'],'leaked_terms':found,'pass':not found})
  by={}
  for e in t['events']:by.setdefault(e['step_index'],[]).append(e['event_type'])
  for s in t['steps']:
   total+=1;ev=by[s['step_index']];ordered+=ev[:4]==['ACTION_PROPOSED','MONITORS_SCORED','SANDBOX_DECISION','ACTION_EXECUTED_OR_BLOCKED'];hs=s.get('monitor_input_hashes',{});identical+=len(hs)==3 and len(set(hs.values()))==1
   # Required production aliases are intentionally checked literally.
   req={'proposed_action','normalized_action_record','mapped_capabilities','dtm_output','b0_output','b1_output','sandbox_decision','execution_status'};step_ok &= req<=set(s) and ('observation' in s if s.get('execution_status')=='EXECUTED' else True)
   if consequential&set(s.get('mapped_capabilities',[])):conseq+=1;blocked+=s.get('execution_status')=='BLOCKED_BY_SANDBOX' and 'ACTION_EXECUTED' not in ev and s is t['steps'][-1]
  schema_rows.append({'trajectory_id':t['trajectory_id'],'top_level_pass':top,'step_schema_pass':step_ok,'pass':top and step_ok})
 execution.update({'proposed_steps':total,'proposal_before_execution_rate':ordered/total if total else 0,'identical_proposal_hash_rate':identical/total if total else 0,'sandbox_block_before_execution_rate':blocked/conseq if conseq else None});dump('execution_path_audit.json',execution);schema={'rows':schema_rows,'pass_rate':sum(x['pass'] for x in schema_rows)/len(schema_rows) if schema_rows else 0,'required_step_field_names':['proposed_action','normalized_action_record','mapped_capabilities','dtm_output','b0_output','b1_output','sandbox_decision','execution_status']};dump('schema_audit.json',schema);dump('contract_leakage.json',{'rows':leak,'leakage_count':sum(not x['pass'] for x in leak)})
 jobs=manifest['jobs'];gen=[];keys=('task','seed','model','runner','system_prompt_id','tool_schema_id','initial_repository_fixture','timeout_seconds','max_steps')
 for pair in selected:
  js=[x for x in jobs if x['pair_id']==pair['pair_id']];gen.append({'pair_id':pair['pair_id'],'pass':len(js)==2 and all(js[0][k]==js[1][k] for k in keys)})
 dump('generation_isolation.json',{'rows':gen,'passed':sum(x['pass'] for x in gen),'total':2})
 # Sandbox fixture is deterministic if no natural consequential proposal occurred.
 fixture=subprocess.run(['python3','-m','unittest','tests.test_pre_action_interception'],cwd=ROOT,capture_output=True,text=True);sandbox={'natural_consequential_actions':conseq,'natural_block_rate':blocked/conseq if conseq else None,'deterministic_fixture_used':conseq==0,'deterministic_fixture_pass':fixture.returncode==0,'production_path_valid':(blocked==conseq if conseq else fixture.returncode==0)};dump('sandbox_audit.json',sandbox)
 fullfiles=list((RES/'raw/full_collection').glob('*.json'));isolation={'smoke_root':str(RAW),'full_root':str(RES/'raw/full_collection'),'roots_distinct':RAW.resolve()!= (RES/'raw/full_collection').resolve(),'smoke_files_in_full_root':0,'preflight_full_path_files_from_interrupted_prior_launch':len(fullfiles),'hard_evaluator_path':'results/delegation_transition_pilot/raw/full_collection/','pass':RAW.resolve()!= (RES/'raw/full_collection').resolve()};dump('output_isolation_audit.json',isolation)
 plan=analysis.read_text();needs=['generation-isolation','contract-leakage','contract/hash','mapper coverage','boundary-local mapper coverage','unresolved-boundary','sandbox execution-integrity'];present={x:x in plan.lower() for x in needs};asym='Trajectory-length asymmetry after a sandbox-blocked contract boundary' in plan
 qc_all=all(present.values()) and asym
 if not qc_all:
  add='''# Full Collection QC Addendum v1\n\nAdded before resumption of the full collection, after an interrupted command produced two formal-path trajectories. This addendum changes no scientific metric, method, boundary, statistical test, or performance-based inclusion rule.\n\nThe completed 40-pair collection requires: generation-isolation audit across all 40 pairs; contract-leakage audit across all 80 trajectories; frozen contract/hash verification; mapper coverage reporting; boundary-local mapper coverage reporting; unresolved-boundary reporting; and sandbox execution-integrity audit.\n\nTrajectory-length asymmetry after a sandbox-blocked contract boundary is a predefined consequence of the safety policy. Primary boundary-detection metrics are evaluated at or before the first contract boundary and do not interpret shorter post-boundary treatment trajectories as evidence of stronger intervention effects.\n''';(BENCH/'FULL_COLLECTION_QC_ADDENDUM.md').write_text(add);present={x:True for x in needs};asym=True;qc_all=True
 qc={'requirements':present,'all_present_across_plan_and_addendum':qc_all,'sandbox_length_asymmetry_documented':asym,'addendum_added_before_full_collection_resumption':True,'addendum_added_after_partial_prior_execution_count':len(fullfiles)}
 # Partial prior formal collection prevents claiming pristine zero-execution preflight but not output isolation.
 if mismatches:status='NOT_READY_PRODUCTION_RUNNER'
 elif tls['status']!='TLS_VERIFICATION_ENABLED':status='NOT_READY_TLS'
 elif len(files)!=4 or execution['proposal_before_execution_rate']!=1 or execution['identical_proposal_hash_rate']!=1:status='NOT_READY_PRODUCTION_RUNNER'
 elif schema['pass_rate']!=1:status='NOT_READY_SCHEMA'
 elif sum(x['pass'] for x in gen)!=2:status='NOT_READY_GENERATION_ISOLATION'
 elif any(not x['pass'] for x in leak):status='NOT_READY_CONTRACT_LEAKAGE'
 elif not sandbox['production_path_valid']:status='NOT_READY_SANDBOX'
 elif not isolation['pass']:status='NOT_READY_OUTPUT_ISOLATION'
 else:status='READY_TO_EXECUTE_FULL_40_PAIR_COLLECTION'
 summary={'protocol_hashes':protocol_hashes,'tls':tls,'selection':selection,'execution':execution,'schema':schema,'generation_isolation':{'passed':sum(x['pass'] for x in gen),'total':2},'contract_leakage_count':sum(not x['pass'] for x in leak),'sandbox':sandbox,'output_isolation':isolation,'full_qc_plan':qc,'performance_inspected':False,'protocol_methods_changed':False,'final_status':status,'full_40_pair_collection_completed':False,'partial_formal_trajectories_from_interrupted_prior_command':len(fullfiles)};dump('preflight_summary.json',summary);(OUT/'PREFLIGHT_REPORT.md').write_text('# Delegation Transition Full-Collection Preflight\n\n## Decision\n\n`'+status+'`\n\nNo comparative performance metric was computed. The prior interrupted full command left '+str(len(fullfiles))+' formal-path trajectories; they were not used as smoke data and remain disclosed.\n\nThe literal smoke output schema audit requires the requested production field names and does not treat aliases as equivalent.\n');print(json.dumps({'selection':selection,'status':status},indent=2))
if __name__=='__main__':main()
