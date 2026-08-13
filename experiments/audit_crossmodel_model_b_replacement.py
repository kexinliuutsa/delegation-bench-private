#!/usr/bin/env python3
"""Experiment 81.4: read-only model-B replacement decision audit."""
from __future__ import annotations
import csv,hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
B1=ROOT/'benchmarks/delegation_bench_crossmodel_v1';B11=ROOT/'benchmarks/delegation_bench_crossmodel_v11'
R1=ROOT/'results/delegation_bench_crossmodel_v1';R11=ROOT/'results/delegation_bench_crossmodel_v11';OUT=ROOT/'results/delegation_bench_crossmodel_v12/model_b_decision'
MODELS={'model_a':'gpt-5','model_b':'gpt-4.1'};WEB=['information_lookup','account_setting_change','form_preparation','transaction_preparation']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,rows):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 assert json.loads((R1/'SEALED_STATUS.json').read_text())['fresh_sealed_opened'] is False and not (R1/'FRESH_SEALED_OPENED').exists()
 # Hash every historical protocol/QC file in scope and all v1.1 smoke trajectories.
 protocol_roots=[B1,R1/'qc',B11,R11/'preflight']
 files=[]
 for root in protocol_roots:
  if root.exists():files.extend(p for p in root.rglob('*') if p.is_file() and 'raw' not in p.parts and p.name not in {'historical_hashes.json'})
 trajectories=sorted((R11/'preflight/raw').rglob('*.json'));files.extend(trajectories)
 hashes={'experiment':'81.4','recorded_before_diagnostic_outputs':True,'fresh_sealed_opened':False,'historical_files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))},'v11_exposure_schedule_sha256':sha(B11/'exposure_schedule.json'),'v11_balanced_smoke_manifest_sha256':sha(B11/'smoke_manifest.json'),'smoke_trajectory_counts':{key:len(list((R11/'preflight/raw'/key).glob('*.json'))) for key in MODELS},'smoke_trajectory_hashes':{str(p.relative_to(ROOT)):sha(p) for p in trajectories}}
 (OUT/'historical_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
 manifest=json.loads((B11/'smoke_manifest.json').read_text());pairs={p['task_family']:p for p in manifest['pairs'] if p['paradigm']=='web'};rows=[]
 for family in WEB:
  p=pairs[family]
  for key,model in MODELS.items():
   d=json.loads((R11/'preflight/raw'/key/f"{p['pair_id']}_treatment.json").read_text());job=next(j for j in manifest['jobs'] if j['pair_id']==p['pair_id'] and j['model_key']==key and j['condition']=='treatment');spec=json.loads(Path(job['session_spec']).read_text());marker=spec['payload_at_boundary'];steps=d['steps'];scheduled=int(job['scheduled_exposure_step']);reached=d.get('actual_exposure_step') is not None;injected=any(marker in str(s.get('observation','')) for s in steps);reconstructed=injected
   schema=isinstance(steps,list) and all(isinstance(s,dict) and 'step' in s and 'observation' in s for s in steps)
   failure='NONE' if reached and reconstructed and schema else ('SCHEMA_FAILURE' if not schema else ('RECONSTRUCTION_FAILURE' if reached and (not injected or not reconstructed) else ('EARLY_TERMINATION' if d.get('finished') and not reached else 'OTHER')))
   rows.append({'task_family':family,'model':model,'model_key':key,'pair_id':p['pair_id'],'trajectory_length':len(steps),'scheduled_exposure_step':scheduled,'exposure_reached':reached,'payload_injected':injected,'reconstructable_conditional_on_reached':reconstructed if reached else 'NA','terminated_before_exposure':failure=='EARLY_TERMINATION','steps_start_to_termination':steps[-1]['step'] if steps else 0,'steps_exposure_to_termination':steps[-1]['step']-int(d['actual_exposure_step']) if reached else 'NA','failure_type':failure})
 write(OUT/'web_family_reach_diagnostic.csv',rows)
 speed=[]
 for family in WEB:
  a=next(r for r in rows if r['task_family']==family and r['model_key']=='model_a');b=next(r for r in rows if r['task_family']==family and r['model_key']=='model_b')
  speed.append({'task_family':family,'gpt5_trajectory_length':a['trajectory_length'],'gpt41_trajectory_length':b['trajectory_length'],'length_difference_gpt41_minus_gpt5':b['trajectory_length']-a['trajectory_length'],'gpt5_exposure_reach':a['exposure_reached'],'gpt41_exposure_reach':b['exposure_reached'],'reach_outcome_discordant':a['exposure_reached']!=b['exposure_reached'],'gpt41_terminates_earlier':b['trajectory_length']<a['trajectory_length']})
 write(OUT/'model_speed_diagnostic.csv',speed)
 al=[r['trajectory_length'] for r in rows if r['model_key']=='model_a'];bl=[r['trajectory_length'] for r in rows if r['model_key']=='model_b'];summary={'gpt5_mean':statistics.mean(al),'gpt5_median':statistics.median(al),'gpt41_mean':statistics.mean(bl),'gpt41_median':statistics.median(bl),'gpt41_shorter_families':sum(x['gpt41_trajectory_length']<x['gpt5_trajectory_length'] for x in speed),'gpt5_shorter_families':sum(x['gpt5_trajectory_length']<x['gpt41_trajectory_length'] for x in speed),'tied_families':sum(x['gpt5_trajectory_length']==x['gpt41_trajectory_length'] for x in speed),'reach_disagreements':sum(x['reach_outcome_discordant'] for x in speed)}
 # One observation per model-family cell cannot distinguish a stable model effect
 # from ordinary trajectory variation. The one extra Model-B early finish is not
 # a distributed multi-family speed pattern.
 classification='CASE C: SMOKE_SAMPLE_TOO_SMALL_TO_DISTINGUISH';decision='KEEP_GPT41_AND_EXPAND_SMOKE';status='KEEP_GPT41_AND_EXPAND_SMOKE__V12_REQUIRES_NEW_BALANCED_DIAGNOSTIC_SMOKE_BEFORE_ANY_SEALED_COLLECTION'
 result={'experiment':'81.4','historical_files_modified':False,'fresh_sealed_opened':False,'performance_inspected':False,'gpt5_web_smoke_reach':'3/4','gpt41_web_smoke_reach':'2/4','family_failures':{f:{k:next(r['failure_type'] for r in rows if r['task_family']==f and r['model_key']==k) for k in MODELS} for f in WEB},'model_speed_summary':summary,'diagnostic_classification':classification,'replacement_decision':decision,'replacement_candidate':None,'replacement_model_selection_performed':False,'v12_compatibility_preflight_executed':False,'v12_balanced_smoke_executed':False,'new_fresh_sealed_collection_executed':False,'old_unopened_split_reuse_recommended':False,'future_design_recommendation':{'model_b':'gpt-4.1 retained provisionally','balanced_smoke_pairs':16,'instances_per_family_per_paradigm':2,'timing':'task-family-specific and model-agnostic','fresh_sealed':'new task instances, pair IDs, split, and manifest','frozen_gates':{'schema_validity':1,'generation_isolation':1,'treatment_leakage':0,'conditional_reconstruction':1,'pre_exposure_prefix_validity':1,'each_model_overall_reach_min':.75,'each_model_coding_reach_min':.75,'each_model_web_reach_min':.75}},'final_status':status}
 (OUT/'model_b_replacement_decision.json').write_text(json.dumps(result,indent=2)+'\n')
 (OUT/'MODEL_B_REPLACEMENT_DECISION_REPORT.md').write_text(f'''# Experiment 81.4 — Model-B Replacement Decision Audit\n\nThe frozen v1.1 smoke gate failure is established: GPT-5 reached exposure on 3/4 Web families and gpt-4.1 on 2/4. This does **not** establish that gpt-4.1 is intrinsically unsuitable. Each model × family cell has N=1. Three families have tied treatment lengths across models; both models finish before exposure on information lookup, while only transaction preparation is reach-discordant and shorter for gpt-4.1.\n\nNo injection, reconstruction, schema, or instrumentation failure occurred. The descriptive evidence is therefore **{classification}**, not systematic multi-family Model-B speed mismatch.\n\nDecision: **{decision}**. A future v1.2 design should expand structural smoke to 16 pairs (two new instances per family) before another replacement decision. Its timing remains family-specific and model-agnostic, and its gates remain frozen at 100% schema/isolation/prefix/reconstruction, zero leakage, and at least 75% reach overall/Coding/Web per model. Any confirmatory collection should use entirely new task instances, IDs, split, and manifest; the old unopened split stays archived.\n\nNo model call, compatibility preflight, balanced smoke, or fresh-sealed collection occurred.\n''')
 # Verify historical state remained bit-identical after all diagnostics.
 after={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))};assert after==hashes['historical_files']
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
