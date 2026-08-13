#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));from delegation_bench_crossmodel_v1_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--split',choices=['smoke','fresh-sealed'],default='smoke');z=a.parse_args();manifest=json.loads((BENCH/'collection_manifest.json').read_text());split=json.loads((BENCH/'split.json').read_text());ids=split['development_smoke'] if z.split=='smoke' else split['fresh_sealed']; rows=[]
 for key,model in MODELS.items():
  root=RESULTS/('smoke' if z.split=='smoke' else 'raw')/key
  for pid in ids:
   jobs={j['condition']:j for j in manifest['jobs'] if j['pair_id']==pid and j['model']==model}; vals={}
   for c,j in jobs.items():
    p=root/f'{pid}_{c}.json'
    try: vals[c]=json.loads(p.read_text())
    except Exception: vals[c]=None
   complete=all(vals.values());schema=complete and all(isinstance(v.get('steps'),list) and v.get('model')==model and not v.get('synthetic') for v in vals.values())
   isolation=complete and all(jobs['control'][f]==jobs['treatment'][f] for f in ['task','seed','model','system_prompt','tool_schema','runner','max_steps','timeout_seconds','fixture_sha256'])
   treatment=vals.get('treatment') or {}; control=vals.get('control') or {}; exp=treatment.get('actual_exposure_step')
   # "Shared prefix" is a causal-input property: identical initial fixture, prompt,
   # seed, runner and no boundary payload before the scheduled step. Agent actions
   # may nevertheless diverge, as the frozen v1 pre-variation audit anticipated.
   scheduled=jobs['treatment']['scheduled_exposure_step']; before=lambda v:[s for s in v.get('steps',[]) if s['step']<scheduled]
   boundary_terms=[json.loads(Path(jobs['treatment']['session_spec']).read_text())['payload_at_boundary']]
   prefix=bool(complete and isolation and all(not any(t in str(s.get('observation','')) for t in boundary_terms) for v in vals.values() for s in before(v)))
   leaked=complete and any(any(term in json.dumps(v).lower() for term in ['treatment condition','control condition','pair condition','expected boundary']) for v in vals.values())
   rows.append({'model_key':key,'model':model,'pair_id':pid,'complete':complete,'schema_valid':schema,'generation_isolation':isolation,'actual_exposure_observable':bool(exp),'pre_exposure_shared_prefix':prefix,'tool_protocol_compatible':schema,'treatment_leakage':bool(leaked),'synthetic':any((v or {}).get('synthetic',False) for v in vals.values())})
 summary={key:{'pairs':sum(r['model_key']==key for r in rows),'complete':sum(r['model_key']==key and r['complete'] for r in rows),'schema_rate':sum(r['model_key']==key and r['schema_valid'] for r in rows)/len(ids),'generation_isolation_rate':sum(r['model_key']==key and r['generation_isolation'] for r in rows)/len(ids),'exposure_reconstruction_rate':sum(r['model_key']==key and r['actual_exposure_observable'] for r in rows)/len(ids),'pre_exposure_prefix_rate':sum(r['model_key']==key and r['pre_exposure_shared_prefix'] for r in rows)/len(ids),'leakage_count':sum(r['model_key']==key and r['treatment_leakage'] for r in rows),'synthetic_count':sum(r['model_key']==key and r['synthetic'] for r in rows)} for key in MODELS}
 ready=all(v['complete']==len(ids) and v['schema_rate']==1 and v['generation_isolation_rate']==1 and v['exposure_reconstruction_rate']>0 and v['pre_exposure_prefix_rate']==1 and not v['leakage_count'] and not v['synthetic_count'] for v in summary.values());status='READY_FOR_FRESH_SEALED_COLLECTION' if ready else ('SECOND_MODEL_PROTOCOL_INCOMPATIBLE' if summary['model_b']['schema_rate']<1 else 'SMOKE_QC_FAILED');out={'split':z.split,'performance_inspected':False,'prefix_definition':'identical frozen causal inputs and no treatment payload observable before scheduled exposure; behavioral identity is not required','early_termination_before_exposure_is_reported_not_fabricated':True,'rows':rows,'models':summary,'status':status};(RESULTS/'qc'/f'{z.split}_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'models':summary,'status':status},indent=2))
if __name__=='__main__':main()
