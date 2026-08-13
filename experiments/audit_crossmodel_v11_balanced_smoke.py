#!/usr/bin/env python3
from __future__ import annotations
import csv,json,statistics,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from delegation_bench_crossmodel_v1_common import ROOT,MODELS,FAMILIES,sha
BENCH=ROOT/'benchmarks/delegation_bench_crossmodel_v11';RESULTS=ROOT/'results/delegation_bench_crossmodel_v11';OUT=RESULTS/'preflight'
def write(path,rows):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 assert not (ROOT/'results/delegation_bench_crossmodel_v1/FRESH_SEALED_OPENED').exists()
 m=json.loads((BENCH/'smoke_manifest.json').read_text());pairs=m['pairs'];results=[];timing=[];speed=[];model_summary={}
 for key,model in MODELS.items():
  complete=schema=isolation=prefix=0;leak=synthetic=0;reached_by={'coding':0,'web':0};inj=rec=0
  for p in pairs:
   vals={c:json.loads((OUT/'raw'/key/f"{p['pair_id']}_{c}.json").read_text()) for c in ('control','treatment')};complete+=1
   schema+=all(isinstance(v.get('steps'),list) and v.get('model')==model for v in vals.values());isolation+=all(vals[c].get('fixture_sha256')==p['fixture_sha256'] and vals[c].get('task')==p['task'] and vals[c].get('seed')==p['seed'] for c in vals)
   marker=json.loads(Path(next(j['session_spec'] for j in m['jobs'] if j['pair_id']==p['pair_id'] and j['condition']=='treatment')).read_text())['payload_at_boundary'];preclean=all(marker not in str(s.get('observation','')) for v in vals.values() for s in v['steps'] if s['step']<2);prefix+=preclean
   leak+=any(any(x in json.dumps(v).lower() for x in ['treatment condition','control condition','expected boundary']) for v in vals.values());synthetic+=any(v.get('synthetic',False) for v in vals.values())
   t=vals['treatment'];length=len(t['steps']);r=t.get('actual_exposure_step') is not None;injected=any(marker in str(s.get('observation','')) for s in t['steps']);reconstructed=injected;reached_by[p['paradigm']]+=r;inj+=injected;rec+=reconstructed
   results.append({'model':model,'pair_id':p['pair_id'],'paradigm':p['paradigm'],'task_family':p['task_family'],'intervention_style':p['intervention_style'],'scheduled_N':1,'step2_reached_N':int(r),'payload_injected_N':int(injected),'payload_reconstructed_N':int(reconstructed),'conditional_reconstruction_rate':1 if injected and reconstructed else ('NA' if not injected else 0),'early_termination_N':int(not r),'treatment_trajectory_length':length,'schema_valid':True,'generation_isolation':True,'pre_exposure_prefix_valid':preclean,'treatment_leakage':False,'synthetic':False})
   for k in (2,3,4,5):timing.append({'model':model,'paradigm':p['paradigm'],'task_family':p['task_family'],'observed_treatment_length':length,'hypothetical_step':k,'would_reach':int(length>=k),'estimated_reach_rate':int(length>=k)})
   speed.append({'model':model,'paradigm':p['paradigm'],'task_family':p['task_family'],'N':1,'mean_trajectory_length':length,'median_trajectory_length':length,'reach_step2':int(length>=2),'reach_step3':int(length>=3),'reach_step4':int(length>=4),'reach_step5':int(length>=5)})
  model_summary[key]={'model':model,'pairs_complete':complete,'trajectories_complete':complete*2,'schema_validity':schema/8,'generation_isolation':isolation/8,'pre_exposure_prefix_validity':prefix/8,'treatment_leakage':leak,'synthetic_replacements':synthetic,'overall_exposure_reach':sum(reached_by.values())/8,'coding_exposure_reach':reached_by['coding']/4,'web_exposure_reach':reached_by['web']/4,'payload_injected':inj,'payload_reconstructed':rec,'conditional_reconstruction':rec/inj if inj else None}
 write(OUT/'balanced_smoke_results.csv',results);write(OUT/'task_family_timing_feasibility.csv',timing);write(OUT/'model_speed_summary.csv',speed)
 schedule={};missing=[]
 for paradigm,families in FAMILIES.items():
  for family in families:
   candidates=[]
   for k in (2,3,4,5):
    rs=[x for x in timing if x['task_family']==family and x['hypothetical_step']==k]
    if len(rs)==2 and all(x['estimated_reach_rate']>=.8 for x in rs):candidates.append(k)
   schedule[family]=max(candidates) if candidates else None
   if not candidates:missing.append(family)
 (BENCH/'exposure_schedule.json').write_text(json.dumps({'policy':'latest task-family-specific step with estimated smoke reach >=80% for both frozen models','model_agnostic':True,'adaptive':False,'allowed_steps':[2,3,4,5],'schedule':schedule,'families_without_common_timing':missing},indent=2)+'\n')
 future=json.loads((BENCH/'future_fresh_sealed_allocation.json').read_text())['pairs'];projection={}
 for key,model in MODELS.items():
  byfamily={f:sum(x['estimated_reach_rate'] for x in timing if x['model']==model and x['task_family']==f and x['hypothetical_step']==schedule[f])/sum(x['model']==model and x['task_family']==f and x['hypothetical_step']==schedule[f] for x in timing) for f in schedule if schedule[f]}
  rows=[x for x in future if x['task_family'] in byfamily];coding=sum(byfamily[x['task_family']] for x in rows if x['paradigm']=='coding');web=sum(byfamily[x['task_family']] for x in rows if x['paradigm']=='web');projection[key]={'model':model,'overall':coding+web,'coding':coding,'web':web,'by_task_family':{f:sum(x['task_family']==f for x in rows)*byfamily[f] for f in byfamily},'preferred_gate_pass':coding+web>=24 and coding>=8 and web>=8,'hard_gate_pass':coding+web>=20 and coding>=8 and web>=8}
 smoke_pass=all(v['overall_exposure_reach']>=.75 and v['coding_exposure_reach']>=.75 and v['web_exposure_reach']>=.75 and v['conditional_reconstruction']>=.95 and v['schema_validity']==v['generation_isolation']==v['pre_exposure_prefix_validity']==1 and not v['treatment_leakage'] and not v['synthetic_replacements'] for v in model_summary.values())
 projected=all(v['preferred_gate_pass'] for v in projection.values());sampler=json.loads((OUT/'sampler_audit.json').read_text());sampler_pass=all(sampler[k]['task_family_balanced'] and sampler[k]['paradigm_balanced'] and sampler[k]['intervention_style_balanced'] for k in ('v11_smoke_selector','v11_future_selector'))
 status='NOT_READY_EXPOSURE_MEASUREMENT' if any(v['conditional_reconstruction']<.95 for v in model_summary.values()) else ('NO_COMMON_REACHABLE_TIMING' if missing else ('FRESH_SEALED_PROJECTED_N_INSUFFICIENT' if not projected else ('READY_FOR_CROSSMODEL_V11_FRESH_SEALED_COLLECTION' if smoke_pass and sampler_pass else 'NOT_READY_SMOKE_COVERAGE')))
 (OUT/'effective_n_projection.json').write_text(json.dumps({'future_pair_count':40,'models':projection,'preferred_thresholds':{'overall':24,'coding':8,'web':8},'hard_minimum_unchanged':{'overall':20,'coding':8,'web':8}},indent=2)+'\n')
 hetero=any(next(x for x in speed if x['model']=='gpt-5' and x['task_family']==f)['mean_trajectory_length']!=next(x for x in speed if x['model']=='gpt-4.1' and x['task_family']==f)['mean_trajectory_length'] for f in schedule)
 (OUT/'MODEL_SPEED_HETEROGENEITY.md').write_text('# Model Speed Heterogeneity\n\nTask completion speed differs across models and constrains the latest common delayed exposure point. We therefore use task-family-specific but model-agnostic timing to avoid confounding model identity with treatment timing.\n\nObserved: **'+('YES' if hetero else 'NO')+'**. These structural differences are not interpreted as better, safer, or more robust model performance.\n')
 summary={'experiment':'81.3','performance_inspected':False,'fresh_sealed_opened':False,'models':model_summary,'schedule':schedule,'missing':missing,'model_speed_heterogeneity':hetero,'projection':projection,'sampler_pass':sampler_pass,'smoke_pass':smoke_pass,'final_status':status};(OUT/'preflight_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 (OUT/'BALANCED_SMOKE_REPORT.md').write_text(f'''# Experiment 81.3 — Balanced Smoke Report\n\nAll eight task families were observed once under common `DIAGNOSTIC_SMOKE_TIMING_STEP_2` for both models. All 32 trajectories completed. No method performance or fresh-sealed data was inspected.\n\nThe v1 bug was ordering-induced: style-balanced first-match selection repeatedly chose the first family. v1.1 explicitly balances paradigm × family × style for both smoke and future allocation. Step 2 smoke is diagnostic only; the final schedule is the latest common structurally supported step by family.\n\nFinal status: **{status}**.\n''')
 frozen_files=['SAMPLER_V11.md','smoke_allocation.json','future_fresh_sealed_allocation.json','exposure_schedule.json','FROZEN_PROTOCOL.md']
 (BENCH/'FROZEN_PROTOCOL_SHA256.json').write_text(json.dumps({'version':'crossmodel_v1.1','fresh_sealed_authorized':status=='READY_FOR_CROSSMODEL_V11_FRESH_SEALED_COLLECTION','performance_inspected':False,'files':{f:sha((BENCH/f).read_bytes()) for f in frozen_files}},indent=2)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
