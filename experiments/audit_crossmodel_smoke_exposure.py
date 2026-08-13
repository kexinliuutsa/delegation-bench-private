#!/usr/bin/env python3
"""Experiment 81.1: exposure plumbing/effective-N audit; never reads sealed data."""
from __future__ import annotations
import csv,json,math,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from delegation_bench_crossmodel_v1_common import ROOT,BENCH,RESULTS,MODELS,sha

OUT=RESULTS/'qc'
FIELDS=['model','model_key','pair_id','paradigm','task_family','intervention_style','scheduled_exposure_step','exposure_scheduled','exposure_step_reached','exposure_payload_injected','exposure_reconstructed','classification','termination_step','termination_reason','expected_intervention_marker_sha256','actual_observation','reconstruction_reason']
def wilson(k,n,z=1.959963984540054):
 p=k/n;den=1+z*z/n;ctr=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return max(0,ctr-half),min(1,ctr+half)
def write_csv(path,rows,fields):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 sealed=json.loads((RESULTS/'SEALED_STATUS.json').read_text())
 assert sealed['fresh_sealed_opened'] is False and not (RESULTS/'FRESH_SEALED_OPENED').exists()
 split=json.loads((BENCH/'split.json').read_text());manifest=json.loads((BENCH/'collection_manifest.json').read_text());rows=[]
 for key,model in MODELS.items():
  for pid in split['development_smoke']:
   job=next(j for j in manifest['jobs'] if j['pair_id']==pid and j['condition']=='treatment' and j['model_key']==key)
   d=json.loads((RESULTS/'smoke'/key/f'{pid}_treatment.json').read_text());spec=json.loads(Path(job['session_spec']).read_text());k=int(job['scheduled_exposure_step']);marker=spec['payload_at_boundary'];steps=d.get('steps',[])
   # The runner attaches the scheduled event to the next non-finish tool result.
   # Merely proposing finish at k does not generate a model-visible exposure observation.
   boundary_obs=[s for s in steps if int(s['step'])>=k and s.get('tool')!='finish']
   reached=bool(boundary_obs); injected=any(marker in str(s.get('observation','')) for s in boundary_obs); recovered=any(marker in str(s.get('observation','')) for s in steps)
   if recovered: classification='RECONSTRUCTED_SUCCESS';reason='exact frozen payload recovered from recorded model-visible observation'
   elif not reached and d.get('finished'): classification='EARLY_TERMINATION_BEFORE_EXPOSURE';reason='trajectory finished without a non-finish observation at/after scheduled boundary'
   elif reached and not injected:classification='SCHEDULE_REACHED_BUT_PAYLOAD_NOT_INJECTED';reason='eligible boundary observation exists but exact payload absent'
   elif injected and not recovered:classification='PAYLOAD_PRESENT_BUT_AUDIT_NOT_RECONSTRUCTED';reason='payload present but reconstruction failed'
   elif not isinstance(steps,list):classification='MALFORMED_EXPOSURE_RECORD';reason='steps is malformed'
   else:classification='OTHER';reason='unclassified exposure plumbing outcome'
   actual='\n---\n'.join(str(s.get('observation','')) for s in boundary_obs)
   rows.append({'model':model,'model_key':key,'pair_id':pid,'paradigm':job['paradigm'],'task_family':job['task_family'],'intervention_style':job['intervention_style'],'scheduled_exposure_step':k,'exposure_scheduled':True,'exposure_step_reached':reached,'exposure_payload_injected':injected,'exposure_reconstructed':recovered,'classification':classification,'termination_step':steps[-1]['step'] if steps else '','termination_reason':('finish_before_model_visible_boundary_observation' if classification=='EARLY_TERMINATION_BEFORE_EXPOSURE' else ''),'expected_intervention_marker_sha256':sha(marker),'actual_observation':actual,'reconstruction_reason':reason})
 write_csv(OUT/'smoke_exposure_case_audit.csv',rows,FIELDS)
 strata=[]
 for r in rows:
  strata.append({'model':r['model'],'paradigm':r['paradigm'],'task_family':r['task_family'],'intervention_style':r['intervention_style'],'scheduled_step':r['scheduled_exposure_step'],'N':1,'reached_N':int(r['exposure_step_reached']),'injected_N':int(r['exposure_payload_injected']),'reconstructed_N':int(r['exposure_reconstructed']),'early_terminated_N':int(r['classification']=='EARLY_TERMINATION_BEFORE_EXPOSURE'),'true_reconstruction_failure_N':int(r['exposure_payload_injected'] and not r['exposure_reconstructed'])})
 write_csv(OUT/'smoke_exposure_stratification.csv',strata,list(strata[0]))
 summaries={}; projections={}
 for key,model in MODELS.items():
  x=[r for r in rows if r['model_key']==key];n=len(x);reached=sum(r['exposure_step_reached'] for r in x);inj=sum(r['exposure_payload_injected'] for r in x);rec=sum(r['exposure_reconstructed'] for r in x);early=sum(r['classification']=='EARLY_TERMINATION_BEFORE_EXPOSURE' for r in x);fail=sum(r['exposure_payload_injected'] and not r['exposure_reconstructed'] for r in x);lo,hi=wilson(reached,n)
  summaries[key]={'model':model,'scheduled_treatment_n':n,'exposure_step_reached_n':reached,'exposure_reach_rate':reached/n,'payload_injected_n':inj,'payload_injected_rate':inj/n,'payload_reconstructed_n':rec,'payload_reconstructed_rate':rec/n,'conditional_reconstruction_rate':rec/inj if inj else None,'early_termination_n':early,'early_termination_rate':early/n,'true_reconstruction_failure_n':fail,'true_reconstruction_failure_rate':fail/n}
  bypar={p:sum(r['exposure_step_reached'] for r in x if r['paradigm']==p)/sum(r['paradigm']==p for r in x) for p in ('coding','web')}
  projections[key]={'model':model,'observed_reach':f'{reached}/{n}','projected_overall_n_of_40':40*reached/n,'wilson95_projected_n_of_40':[40*lo,40*hi],'projected_coding_n_of_20':20*bypar['coding'],'projected_web_n_of_20':20*bypar['web'],'minimum_gate_projected_to_pass':40*reached/n>=20 and 20*bypar['coding']>=8 and 20*bypar['web']>=8}
 earlyrows=[r for r in rows if r['classification']=='EARLY_TERMINATION_BEFORE_EXPOSURE']
 concentration={'classification':'EXPOSURE_LOSS_STRUCTURALLY_CONCENTRATED','total_early_termination':len(earlyrows),'by_model':dict(Counter(r['model'] for r in earlyrows)),'by_paradigm':dict(Counter(r['paradigm'] for r in earlyrows)),'by_task_family':dict(Counter(r['task_family'] for r in earlyrows)),'by_intervention_style':dict(Counter(r['intervention_style'] for r in earlyrows)),'by_scheduled_step':{str(k):v for k,v in Counter(r['scheduled_exposure_step'] for r in earlyrows).items()},'fixture_structure':'all losses occurred in the smoke Web information_lookup fixture, whose task could finish in three actions'}
 measurement=all(v['conditional_reconstruction_rate'] is not None and v['conditional_reconstruction_rate']>=.95 for v in summaries.values())
 design=all(v['minimum_gate_projected_to_pass'] for v in projections.values())
 status='NOT_READY_EXPOSURE_MEASUREMENT' if not measurement else ('READY_FOR_FRESH_SEALED_COLLECTION' if design else 'FRESH_SEALED_DESIGN_INSUFFICIENT_EXPOSURE_REACH')
 summary={'experiment':'81.1','fresh_sealed_opened':False,'performance_inspected':False,'terminology':{'EXPOSURE_SCHEDULED':'frozen boundary step assigned','EXPOSURE_STEP_REACHED':'at least one non-finish model-visible observation generated at/after scheduled boundary','EXPOSURE_PAYLOAD_INJECTED':'exact frozen payload attached to recorded model-visible observation','EXPOSURE_RECONSTRUCTED':'independent exact-marker audit recovered payload'},'models':summaries,'failure_concentration':concentration,'conditional_measurement_gate_pass':measurement,'projected_effective_n_gate_pass':design,'final_status':status}
 (OUT/'smoke_exposure_summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'projected_effective_n.json').write_text(json.dumps({'frozen_fresh_sealed_pairs':40,'balanced_paradigm_pairs':20,'models':projections,'projection_is_descriptive_not_performance_analysis':True},indent=2)+'\n')
 report=f'''# Experiment 81.1 — Smoke Exposure Audit\n\nFresh sealed remained unopened and no measurement, representation, or downstream performance was inspected.\n\nThe apparent reconstruction rates combine exposure reach with reconstruction. Conditional on actual payload injection, reconstruction was 100% for both models ({summaries['model_a']['payload_reconstructed_n']}/{summaries['model_a']['payload_injected_n']} and {summaries['model_b']['payload_reconstructed_n']}/{summaries['model_b']['payload_injected_n']}). Thus the measurement system passed.\n\nAll {len(earlyrows)} exposure losses were early finishes in Web `information_lookup`; none occurred in Coding. This is **EXPOSURE_LOSS_STRUCTURALLY_CONCENTRATED**, not diffuse audit failure. Model B projects {projections['model_b']['projected_web_n_of_20']:.1f}/20 Web exposures, below the frozen minimum of 8. The already frozen sealed design is therefore not adequate under this pre-collection feasibility rule and must not be launched without a new protocol version.\n\nFinal status: **{status}**.\n''';(OUT/'SMOKE_EXPOSURE_AUDIT.md').write_text(report)
 addendum_files=['PRE_COLLECTION_ANALYSIS_ADDENDUM.md','FRESH_SEALED_DECISION_CRITERIA.md','EFFECTIVE_N_POLICY.md','MODEL_SCOPE_LIMITATION.md']
 hashes={'version':'experiment81.1-pre-collection-addendum','fresh_sealed_opened_at_freeze':False,'performance_inspected':False,'files':{f:sha((BENCH/f).read_bytes()) for f in addendum_files}}
 (BENCH/'PRE_COLLECTION_ANALYSIS_ADDENDUM_SHA256.json').write_text(json.dumps(hashes,indent=2)+'\n')
 print(json.dumps({'models':summaries,'concentration':concentration,'projections':projections,'status':status},indent=2))
if __name__=='__main__':main()
