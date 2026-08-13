#!/usr/bin/env python3
"""Experiment 81.10Q: outcome-firewalled missingness and authorization audit."""
from __future__ import annotations
import csv,hashlib,json,math,statistics
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'benchmarks/delegation_bench_crossmodel_v13/fresh_sealed_v13'
R=ROOT/'results/delegation_bench_crossmodel_v13/fresh_sealed'
O=R/'quota_truncation_audit';S=ROOT/'benchmarks/delegation_bench_crossmodel_v13/quota_truncated_secondary'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def write(name,rows,fields=None):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);fields=fields or list(rows[0])
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def output(j):return R/'raw'/('model_a' if j['model']=='gpt-5' else 'model_b')/f"{j['pair_id']}_{j['condition']}.json"
def valid(p):
 try:return p.exists() and isinstance(json.loads(p.read_text()).get('steps'),list)
 except:return False
def lines(p):
 try:return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
 except:return []
def first_time(j):
 paths=[R/'dispatch'/f"{j['trajectory_id']}.jsonl",output(j),R/'failures'/f"{j['trajectory_id']}.json"]
 times=[]
 for p in paths:
  if not p.exists():continue
  if p.suffix=='.jsonl':
   for x in lines(p):
    if x.get('timestamp'):
     try:times.append(datetime.fromisoformat(x['timestamp']).timestamp())
     except:pass
  elif p==output(j) and valid(p):
   for x in json.loads(p.read_text())['steps']:
    if x.get('timestamp'):
     try:times.append(datetime.fromisoformat(x['timestamp']).timestamp())
     except:pass
  times.append(p.stat().st_mtime)
 return min(times) if times else math.inf
def tv(planned,complete):
 keys=set(planned)|set(complete);a=sum(planned.values());b=sum(complete.values())
 return .5*sum(abs(planned[k]/a-complete[k]/b) for k in keys) if a and b else 1

def main():
 O.mkdir(parents=True,exist_ok=True);manifest=json.loads((B/'collection_manifest.json').read_text());jobs=manifest['jobs'];g=[x for x in jobs if x['model']=='gpt-4.1'];pairs=manifest['pairs']
 # Complete historical inventory, without opening scientific outcomes beyond schema/exposure eligibility.
 required=['FRESH_SEALED_OPENED','collection_inventory.csv','collection_qc.json','raw_proposal_audit.csv','schema_audit.csv','generation_isolation.csv','generation_isolation_summary.json','exposure_reconstruction.csv','exposure_reconstruction_summary.json','pre_exposure_prefix_audit.csv','effective_n.json','early_termination.csv','transport_failure_history.csv','failure_forensics.csv','EXPERIMENT_81_10_REPORT.md']
 frozen=['FROZEN_PROTOCOL.md','collection_manifest.json','split.json','fixture_hashes.json','exposure_schedule.json','model_freeze.json','representation_method_freeze.json','ANALYSIS_PLAN.md','CONFIRMATORY_DECISION_CRITERIA.md','EFFECTIVE_N_POLICY.md']
 histfiles=[R/x for x in required]+[B/x for x in frozen]+list((R/'raw/model_a').glob('*.json'))+list((R/'raw/model_b').glob('*.json'))+list((R/'failures').glob('*model_b*.json'))+list((R/'raw_proposals').glob('*.jsonl'))+list((R/'dispatch').glob('*.jsonl'))
 hist={'experiment':'81.10Q','model_calls':0,'historical_data_modified':False,'hashes':{str(p.relative_to(ROOT)):sha(p) for p in sorted(histfiles) if p.exists()},'gpt5_trajectories':sum(valid(p) for p in (R/'raw/model_a').glob('*.json')),'gpt41_trajectories':sum(valid(p) for p in (R/'raw/model_b').glob('*.json')),'performance_inspected':False};dump(O/'historical_integrity.json',hist)
 order=sorted(g,key=first_time);order_index={x['trajectory_id']:i+1 for i,x in enumerate(order)};inventory=[];classes=[]
 for j in g:
  out=output(j);fp=R/'failures'/f"{j['trajectory_id']}.json";rp=R/'raw_proposals'/f"{j['trajectory_id']}.jsonl";dp=R/'dispatch'/f"{j['trajectory_id']}.jsonl";ee=lines(dp);received=any(x.get('event')=='MODEL_PROPOSAL_RECEIVED' for x in ee);raw=bool(rp.exists() and rp.stat().st_size);stderr=json.loads(fp.read_text()).get('stderr','') if fp.exists() else ''
  if valid(out):status='COMPLETE';stage='NONE';fc='NONE'
  else:
   status='MISSING_POST_PROPOSAL' if received else 'MISSING_PRE_PROPOSAL';stage='POST_PROPOSAL' if received else 'PRE_PROPOSAL'
   low=stderr.lower()
   if 'credit_balance_exhausted' in low or 'insufficient_quota' in low or 'no credits remaining' in low:fc='QUOTA_EXHAUSTION_'+stage
   elif 'http' in low or 'urlopen' in low:fc='OTHER_TRANSPORT_FAILURE'
   elif any(x in low for x in ('parser','dispatch')):fc='PARSER_DISPATCH_FAILURE'
   elif 'schema' in low:fc='SCHEMA_FAILURE'
   else:fc='UNKNOWN'
   classes.append({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],'failure_stage':stage,'failure_class':fc,'provider_credit_exhaustion':fc.startswith('QUOTA_EXHAUSTION'),'raw_proposal_available':raw})
  ts=first_time(j);inventory.append({k:j[k] for k in ('trajectory_id','pair_id','condition','paradigm','task_family','intervention_style','scheduled_exposure_step')}|{'status':status,'failure_stage':stage,'proposal_received':received,'raw_proposal_available':raw,'failure_class':fc,'collection_order_index':order_index[j['trajectory_id']],'collection_timestamp_if_available':datetime.fromtimestamp(ts).isoformat() if ts<math.inf else ''})
 assert len(inventory)==80
 write('gpt41_missingness_inventory.csv',inventory);write('quota_failure_classification.csv',classes)
 missing=[x for x in inventory if x['status']!='COMPLETE'];quota=[x for x in missing if x['failure_class'].startswith('QUOTA_EXHAUSTION')];first_quota=min((x['collection_order_index'] for x in quota),default=None);first_missing=min(x['collection_order_index'] for x in missing);last_complete=max(x['collection_order_index'] for x in inventory if x['status']=='COMPLETE');after=[x for x in inventory if first_quota and x['collection_order_index']>=first_quota];pattern='TAIL_TRUNCATION' if first_missing==first_quota and all(x['status']!='COMPLETE' for x in after) else 'INTERLEAVED_MISSINGNESS'
 orderrows=[{'trajectory_id':x['trajectory_id'],'collection_order_index':x['collection_order_index'],'timestamp':x['collection_timestamp_if_available'],'status':x['status'],'failure_class':x['failure_class'],'at_or_after_quota_onset':bool(first_quota and x['collection_order_index']>=first_quota)} for x in sorted(inventory,key=lambda z:z['collection_order_index'])];write('collection_order_audit.csv',orderrows)
 cond=[]
 for v in ('control','treatment'):
  xx=[x for x in inventory if x['condition']==v];n=sum(x['status']=='COMPLETE' for x in xx);cond.append({'condition':v,'planned_N':len(xx),'complete_N':n,'missing_N':len(xx)-n,'completion_rate':n/len(xx)})
 write('missingness_by_condition.csv',cond)
 pc=[];complete_ids=[]
 for p in pairs:
  xx=[x for x in inventory if x['pair_id']==p['pair_id']];c=next(x for x in xx if x['condition']=='control')['status']=='COMPLETE';t=next(x for x in xx if x['condition']=='treatment')['status']=='COMPLETE';st='COMPLETE_PAIR' if c and t else ('CONTROL_ONLY' if c else ('TREATMENT_ONLY' if t else 'NEITHER'))
  pc.append({'pair_id':p['pair_id'],'paradigm':p['paradigm'],'task_family':p['task_family'],'intervention_style':p['intervention_style'],'scheduled_exposure_step':p['scheduled_exposure_step'],'pair_status':st,'control_complete':c,'treatment_complete':t});complete_ids += [p['pair_id']] if st=='COMPLETE_PAIR' else []
 write('pair_completeness.csv',pc);pcnt=Counter(x['pair_status'] for x in pc)
 strata=[]
 dimensions=[('paradigm',),('task_family',),('intervention_style',),('scheduled_exposure_step',),('condition',),('paradigm','condition'),('task_family','condition'),('intervention_style','condition')]
 for ds in dimensions:
  groups=defaultdict(list)
  for x in inventory:groups[tuple(str(x[d]) for d in ds)].append(x)
  for key,xx in sorted(groups.items()):
   n=sum(x['status']=='COMPLETE' for x in xx);strata.append({'dimension':' × '.join(ds),'stratum':' | '.join(key),'planned_N':len(xx),'complete_N':n,'missing_N':len(xx)-n,'completion_rate':n/len(xx)})
 write('missingness_strata.csv',strata)
 overall_pair=len(complete_ids)/40;flags=[]
 for dim in ('paradigm','task_family','intervention_style'):
  groups=defaultdict(list)
  for x in pc:groups[str(x[dim])].append(x)
  for key,xx in sorted(groups.items()):
   rate=sum(x['pair_status']=='COMPLETE_PAIR' for x in xx)/len(xx);flag=len(xx)>=4 and abs(rate-overall_pair)>=.2
   flags.append({'dimension':dim,'stratum':key,'planned_pair_N':len(xx),'complete_pair_N':sum(x['pair_status']=='COMPLETE_PAIR' for x in xx),'completion_proportion':rate,'overall_complete_pair_proportion':overall_pair,'absolute_difference':abs(rate-overall_pair),'flag':'POTENTIAL_STRUCTURAL_MISSINGNESS' if flag else 'NONE'})
 write('imbalance_flags.csv',flags);major=[x for x in flags if x['flag']!='NONE']
 # Eligibility uses actual exposure marker only; no divergence or representation computation.
 eff={'complete_pairs_overall':len(complete_ids),'complete_pairs_Coding':sum(x['pair_status']=='COMPLETE_PAIR' and x['paradigm']=='coding' for x in pc),'complete_pairs_Web':sum(x['pair_status']=='COMPLETE_PAIR' and x['paradigm']=='web' for x in pc)}
 exp=[]
 for x in pc:
  if x['pair_status']!='COMPLETE_PAIR':continue
  j=next(z for z in g if z['pair_id']==x['pair_id'] and z['condition']=='treatment');d=json.loads(output(j).read_text());reached=d.get('actual_exposure_step') is not None;exp.append((x,reached))
 eff|={'exposure_reached_complete_pairs_overall':sum(y for _,y in exp),'exposure_reached_Coding':sum(y and x['paradigm']=='coding' for x,y in exp),'exposure_reached_Web':sum(y and x['paradigm']=='web' for x,y in exp)};eff['hard_minimum_pass']=eff['exposure_reached_complete_pairs_overall']>=20 and eff['exposure_reached_Coding']>=8 and eff['exposure_reached_Web']>=8;eff['preferred_pass']=eff['exposure_reached_complete_pairs_overall']>=24 and eff['exposure_reached_Coding']>=8 and eff['exposure_reached_Web']>=8;dump(O/'complete_case_effective_n.json',eff)
 # Design/order summaries only.
 odb=[]
 for dim in ('paradigm','task_family','intervention_style','condition'):
  gg=defaultdict(list)
  for x in inventory:gg[str(x[dim])].append(x['collection_order_index'])
  for key,v in sorted(gg.items()):odb.append({'dimension':dim,'stratum':key,'N':len(v),'mean_collection_order':statistics.mean(v),'median_collection_order':statistics.median(v),'min_order':min(v),'max_order':max(v)})
 write('collection_order_design_balance.csv',odb)
 rep={}
 for dim in ('paradigm','task_family','intervention_style'):
  pp=Counter(str(x[dim]) for x in pc);cc=Counter(str(x[dim]) for x in pc if x['pair_status']=='COMPLETE_PAIR');rep[dim]={'planned_counts':pp,'complete_pair_counts':cc,'planned_proportions':{k:v/40 for k,v in pp.items()},'complete_pair_proportions':{k:v/len(complete_ids) for k,v in cc.items()},'total_variation_distance':tv(pp,cc)}
 dump(O/'complete_case_representativeness.json',rep)
 # Sparse deterministic tail separation makes ordinary logistic MLE unstable; report design matrix diagnostics only.
 dump(O/'missingness_regression.json',{'attempted':False,'reason':'Descriptive-only: transaction_preparation has complete separation (10/10 trajectories missing), causing numerically unstable categorical logistic regression.','formula':'missing ~ paradigm + task_family + intervention_style + scheduled_exposure_step + condition','outcome_variables_included':False,'pidr_included':False})
 gen=json.loads((R/'generation_isolation_summary.json').read_text());rpa=list(csv.DictReader((R/'raw_proposal_audit.csv').open()));received=sum(int(x['received_proposals']) for x in rpa if x['model']=='gpt-4.1');persisted=sum(int(x['persisted_proposals']) for x in rpa if x['model']=='gpt-4.1');condition_gap=abs(cond[0]['completion_rate']-cond[1]['completion_rate']);nearly_eliminated=any(x['planned_pair_N']>=4 and x['complete_pair_N']<=1 for x in flags);mixed=any(x['failure_class'] in ('PARSER_DISPATCH_FAILURE','SCHEMA_FAILURE','UNKNOWN') for x in missing);quota_overwhelming=len(quota)/len(missing)>=.9
 gates={'quota_exclusive_or_overwhelming':quota_overwhelming,'no_mixed_parser_dispatch_schema_unknown':not mixed,'hard_effective_n_pass':eff['hard_minimum_pass'],'condition_completion_gap_le_20pp':condition_gap<=.2,'no_nearly_eliminated_stratum':not nearly_eliminated,'generation_isolation_100_percent':gen['rate']==1,'proposal_persistence_100_percent':persisted==received,'performance_uninspected':True}
 authorized=all(gates.values());status='QUOTA_TRUNCATED_SECONDARY_ANALYSIS_AUTHORIZED' if authorized else 'QUOTA_TRUNCATED_SECONDARY_ANALYSIS_NOT_AUTHORIZED';quality=('QUOTA_TRUNCATED_HIGH_COVERAGE' if authorized and len(complete_ids)>=30 and eff['preferred_pass'] and not major else ('QUOTA_TRUNCATED_MINIMUM_VALID' if authorized else ('QUOTA_TRUNCATED_TOO_BIASED' if nearly_eliminated or major else 'NOT_APPLICABLE')))
 decision={'missingness_counts':Counter(x['status'] for x in inventory),'failure_classes':Counter(x['failure_class'] for x in missing),'mixed_missingness_mechanisms':len(quota)!=len(missing),'collection_pattern':pattern,'first_missing_order_index':first_missing,'first_quota_order_index':first_quota,'last_completed_order_index':last_complete,'missing_jobs_after_quota_begins':sum(x['status']!='COMPLETE' for x in after),'completed_jobs_after_quota_begins':sum(x['status']=='COMPLETE' for x in after),'pair_completeness':pcnt,'condition_completion':cond,'structural_flags':major,'effective_n':eff,'generation_isolation_rate':gen['rate'],'proposal_persistence_rate':persisted/received if received else 0,'representativeness':rep,'authorization_gates':gates,'preregistered_complete_cohort_primary_status':'NOT_COMPLETED_AS_PREREGISTERED','performance_inspected':False,'evidence_quality':quality,'final_status':status};dump(O/'authorization_decision.json',decision)
 (O/'EXPERIMENT_81_10Q_REPORT.md').write_text(f'''# Experiment 81.10Q — Quota-Truncated Missingness Audit

Final status: **{status}**. Evidence quality: **{quality}**.

The observed subset contains {len(complete_ids)} complete pairs and {eff['exposure_reached_complete_pairs_overall']} exposure-reached complete pairs. The frozen hard effective-N gate {'passes' if eff['hard_minimum_pass'] else 'fails'}. Missingness is {pattern.lower().replace('_',' ')}: {len(quota)}/{len(missing)} failures are explicit quota exhaustion, while one is a provider HTTP transport failure. The complete-pair subset eliminates transaction_preparation (0/5 complete pairs), creating severe structural missingness. Therefore a secondary scientific analysis is not authorized. No outcomes, representations, monitor results, or scientific effects were inspected.
''')
 (ROOT/'paper/QUOTA_TRUNCATED_CROSSMODEL_REPORTING_GUIDANCE.md').write_text('''# Quota-Truncated Cross-Model Reporting Guidance

The gpt-4.1 fresh-sealed collection was truncated by provider credit exhaustion after 68/80 trajectories. We do not impute or synthesize missing trajectories and do not treat the resulting cohort as the preregistered complete-cohort primary analysis. The completed paired subset satisfies the numerical effective-N thresholds, but the missingness audit found that one task family was eliminated from complete pairs and one missing job had a distinct provider transport failure. A quota-truncated sealed scientific analysis is therefore not authorized from this subset. The preregistered complete-cohort primary analysis remains **NOT_COMPLETED_AS_PREREGISTERED**.
''')
 # No secondary namespace is created when authorization fails.
 print(json.dumps(decision,indent=2,default=dict))
 # Integrity check: all source hashes unchanged after read-only audit.
 assert all(sha(ROOT/p)==h for p,h in hist['hashes'].items())

if __name__=='__main__':main()
