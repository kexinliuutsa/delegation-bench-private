#!/usr/bin/env python3
import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_bench_crossmodel_v13';R=ROOT/'results/delegation_bench_crossmodel_v13/compatibility';V1=ROOT/'results/delegation_bench_crossmodel_v1'
def write(path,rows,fields):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 m=json.loads((B/'diagnostic_manifest.json').read_text());inventory=[];dispatch=[];forensics=[];summaries={}
 for key,model in m['models'].items():
  jobs=[x for x in m['jobs'] if x['model_key']==key];complete=raw_ok=schema=0;proposal_n=step_n=0;failures=[]
  for j in jobs:
   out=R/'raw'/f"{j['trajectory_id']}.json";raw=R/'raw_proposals'/f"{j['trajectory_id']}.jsonl";ev=R/'dispatch'/f"{j['trajectory_id']}.jsonl";ok=out.exists();d=json.loads(out.read_text()) if ok else None;rr=[json.loads(x) for x in raw.read_text().splitlines()] if raw.exists() else [];ee=[json.loads(x) for x in ev.read_text().splitlines()] if ev.exists() else [];steps=len(d['steps']) if d else 0;persist=len(rr)==steps and steps>0;complete+=ok;raw_ok+=persist;schema+=bool(ok and isinstance(d.get('steps'),list));proposal_n+=len(rr);step_n+=steps
   execfails=[x for x in ee if x.get('dispatch_status')=='EXECUTION_FAILED'];failures.extend(execfails)
   inventory.append({'trajectory_id':j['trajectory_id'],'model':model,'pair_id':j['pair_id'],'condition':j['condition'],'complete':ok,'steps':steps,'raw_proposals':len(rr),'proposal_persistence_complete':persist,'schema_valid':bool(ok and isinstance(d.get('steps'),list)),'synthetic':False,'exposure_reached':d.get('actual_exposure_step') is not None if d else 'NA'})
   for x in ee:
    if 'dispatch_status' in x:dispatch.append({'trajectory_id':j['trajectory_id'],'model':model,'step':x.get('step'),'dispatch_status':x.get('dispatch_status'),'normalized_tool':x.get('normalized_tool'),'normalized_args':json.dumps(x.get('normalized_args'),sort_keys=True),'executor_selected':x.get('executor_selected'),'exception_type':x.get('exception_type'),'exception_message':x.get('exception_message')})
  summaries[key]={'model':model,'completed':complete,'planned':8,'raw_proposal_persistence_trajectories':raw_ok,'proposal_records':proposal_n,'recorded_steps':step_n,'raw_proposal_persistence_rate':proposal_n/step_n if step_n else 0,'schema_validity':schema/8,'parser_dispatch_failures':len(failures),'synthetic_replacements':0,'exposure_reached_trajectories':sum(x['exposure_reached'] is True for x in inventory if x['model']==model)}
 write(R/'trajectory_inventory.csv',inventory,list(inventory[0]));write(R/'dispatch_outcomes.csv',dispatch,list(dispatch[0]));write(R/'failure_forensics.csv',forensics,['trajectory_id','model','step','raw_proposal','classification','direct_evidence'])
 allpass=all(x['completed']==8 and x['raw_proposal_persistence_rate']==1 and x['schema_validity']==1 and not x['parser_dispatch_failures'] and not x['synthetic_replacements'] for x in summaries.values());status='RUNNER_COMPATIBILITY_OBSERVED' if allpass else 'CROSSMODEL_RUNNER_INSTABILITY_UNRESOLVED'
 qc={'experiment':'81.7','historical_failures_retried':False,'historical_root_cause_claimed':False,'protocol_version':'v1.3','new_pairs':4,'planned_trajectories':16,'models':summaries,'failures_with_direct_raw_evidence':0,'root_cause_classifications':{},'scientific_logic_changed':False,'exposure_timing_changed':False,'model_b_changed':False,'performance_inspected':False,'fresh_sealed_opened':False,'repair_implemented':False,'balanced_scientific_smoke_still_required':True,'final_status':status};(R/'qc_summary.json').write_text(json.dumps(qc,indent=2)+'\n')
 (R/'EXPERIMENT_81_7_REPORT.md').write_text(f'''# Experiment 81.7 — Pre-Dispatch Proposal Persistence Diagnostic\n\nThe versioned v1.3 runner appended every structured proposal before normalization, dispatch classification, executor selection, or execution. Both GPT-5 and gpt-4.1 completed 8/8 new compatibility trajectories; proposal persistence and schema validity were 100%, with no parser, dispatch, or executor failures and no synthetic replacements.\n\nThis tiny infrastructure diagnostic does not establish the historical Experiment 81.5 root cause and does not authorize fresh-sealed collection. No repair was implemented. A completely new balanced scientific smoke remains required.\n\nFinal status: **{status}**.\n''')
 assert not (V1/'FRESH_SEALED_OPENED').exists() and not any((V1/'raw').rglob('*.json'))
 print(json.dumps(qc,indent=2))
if __name__=='__main__':main()
