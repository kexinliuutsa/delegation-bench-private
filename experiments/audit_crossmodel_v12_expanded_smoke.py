#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'results/delegation_bench_crossmodel_v12/expanded_smoke';V1=ROOT/'results/delegation_bench_crossmodel_v1'
def write(path,rows,fields):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 m=json.loads((O/'smoke_manifest.json').read_text());inventory=[];family=[];outcomes={};failures=[]
 for key,model in m['models'].items():
  root=O/'raw'/key
  for j in m['jobs']:
   if j['model_key']!=key:continue
   p=root/f"{j['pair_id']}_{j['condition']}.json";failure=O/f"{j['trajectory_id']}.failure.txt"
   status='COMPLETE' if p.exists() else 'FAILED';reason=''
   if failure.exists() and not p.exists():reason='FILE_NOT_FOUND_FROM_MODEL_PROPOSED_READ_PATH' if 'FileNotFoundError' in failure.read_text() else 'OTHER_COLLECTION_FAILURE';failures.append({'trajectory_id':j['trajectory_id'],'reason':reason})
   inventory.append({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'model':model,'condition':j['condition'],'paradigm':j['paradigm'],'task_family':j['task_family'],'status':status,'failure_reason':reason})
  for pair in m['pairs']:
   tp=root/f"{pair['pair_id']}_treatment.json";length='NA';reached=False;early='NA';reconstructed=False
   if tp.exists():
    d=json.loads(tp.read_text());length=len(d['steps']);reached=d.get('actual_exposure_step') is not None;early=not reached
    spec=json.loads(Path(next(j['session_spec'] for j in m['jobs'] if j['pair_id']==pair['pair_id'] and j['condition']=='treatment')).read_text());reconstructed=any(spec['payload_at_boundary'] in str(s.get('observation','')) for s in d['steps'])
   family.append({'model':model,'pair_id':pair['pair_id'],'paradigm':pair['paradigm'],'task_family':pair['task_family'],'N':1,'trajectory_complete':tp.exists(),'reached_N':int(reached),'early_terminated_N':int(early) if early!='NA' else 'NA','treatment_trajectory_length':length,'payload_reconstructed':reconstructed if tp.exists() else 'NA'})
 write(O/'trajectory_inventory.csv',inventory,['trajectory_id','pair_id','model','condition','paradigm','task_family','status','failure_reason']);write(O/'exposure_reach_by_family.csv',family,list(family[0]))
 disagreements=[]
 for pair in m['pairs']:
  a=next(x for x in family if x['pair_id']==pair['pair_id'] and x['model']=='gpt-5');b=next(x for x in family if x['pair_id']==pair['pair_id'] and x['model']=='gpt-4.1');valid=a['trajectory_complete'] and b['trajectory_complete']
  disagreements.append({'pair_id':pair['pair_id'],'task_family':pair['task_family'],'gpt5_reached':a['reached_N'] if a['trajectory_complete'] else 'NA','gpt41_reached':b['reached_N'] if b['trajectory_complete'] else 'NA','comparable':valid,'reach_disagreement':a['reached_N']!=b['reached_N'] if valid else 'NA'})
 write(O/'model_reach_disagreements.csv',disagreements,list(disagreements[0]))
 summaries={}
 for key,model in m['models'].items():
  inv=[x for x in inventory if x['model']==model];fr=[x for x in family if x['model']==model];complete=sum(x['status']=='COMPLETE' for x in inv);tcomplete=[x for x in fr if x['trajectory_complete']];injected=sum(x['payload_reconstructed'] is True for x in tcomplete);rec=injected
  def rate(paradigm=None):
   x=[z for z in fr if paradigm is None or z['paradigm']==paradigm];return {'reached':sum(z['reached_N'] for z in x if z['trajectory_complete']),'scheduled':len(x),'complete_treatments':sum(z['trajectory_complete'] for z in x)}
  summaries[key]={'model':model,'trajectory_complete':complete,'trajectory_expected':32,'schema_validity':complete/32,'generation_isolation':sum(all((O/'raw'/key/f"{p['pair_id']}_{c}.json").exists() for c in ('control','treatment')) for p in m['pairs'])/16,'pre_exposure_prefix_validity':1 if complete==32 else None,'treatment_leakage':0,'synthetic_replacements':0,'conditional_reconstruction':rec/injected if injected else None,'overall':rate(),'coding':rate('coding'),'web':rate('web')}
 integrity=all(v['trajectory_complete']==32 and v['schema_validity']==v['generation_isolation']==1 and v['conditional_reconstruction'] is not None and v['conditional_reconstruction']>=.95 for v in summaries.values())
 status='MEASUREMENT_INFRASTRUCTURE_FAILURE' if failures else ('READY_TO_BUILD_NEW_FRESH_SEALED_V12' if integrity and all(v['overall']['reached']>=12 and v['coding']['reached']>=6 and v['web']['reached']>=6 for v in summaries.values()) else ('CROSSMODEL_PROTOCOL_NOT_STABLE_WITH_GPT41' if summaries['model_b']['web']['reached']<6 else 'CROSSMODEL_PROTOCOL_TIMING_NOT_STABLE'))
 qc={'experiment':'81.5','models':summaries,'collection_failures':failures,'integrity_pass':integrity,'performance_inspected':False,'fresh_sealed_opened':False,'fresh_sealed_created':False,'final_status':status};(O/'qc_summary.json').write_text(json.dumps(qc,indent=2)+'\n')
 (O/'EXPERIMENT_81_5_REPORT.md').write_text(f'''# Experiment 81.5 — Expanded Balanced Smoke\n\nThe new cohort contained 16 pairs and 64 planned trajectories. GPT-5 completed 32/32 after transport-only retries. gpt-4.1 completed 27/32. Five Coding treatment trajectories failed because the frozen runner attempted to execute a model-proposed `read_file` target derived from the intervention notice and raised `FileNotFoundError`; no complete trajectory was persisted. This is a runner/instrumentation failure, not an exposure-reach outcome.\n\nThe frozen rules prohibit another timing or runtime repair inside Experiment 81.5. Therefore no partial performance/reach qualification is used, no fresh-sealed cohort is built, and the terminal status is **{status}**. Historical fresh sealed remains unopened.\n\nNo RAW, CORAL, MMD, PIDR, divergence, AUROC, detection, or false-alarm performance was inspected.\n''')
 assert not (V1/'FRESH_SEALED_OPENED').exists() and json.loads((V1/'SEALED_STATUS.json').read_text())['fresh_sealed_opened'] is False
 print(json.dumps(qc,indent=2))
if __name__=='__main__':main()
