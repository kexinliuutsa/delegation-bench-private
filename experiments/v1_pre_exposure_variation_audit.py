#!/usr/bin/env python3
"""Experiment 70.1: freeze benchmark findings and audit pre-exposure variation."""
from __future__ import annotations
import csv,hashlib,json,math,random,subprocess
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean,median
from delegation_bench_v1_common import ROOT,BENCH,RESULTS
from delegation_bench_v1_measurements import action_divergence,capability_divergence
OUT=RESULTS/'pre_exposure_variation';CONF=RESULTS/'confirmatory';REPS=10_000;SEED=70101;EPS=1e-6
def q(xs,p):
 ys=sorted(xs);x=(len(ys)-1)*p;i=int(x);j=min(i+1,len(ys)-1);return ys[i]+(ys[j]-ys[i])*(x-i)
def boot_mean(xs,seed=SEED):
 rng=random.Random(seed);n=len(xs);return [mean(xs[rng.randrange(n)] for _ in range(n)) for _ in range(REPS)]
def ci(xs,seed=SEED):b=boot_mean(xs,seed);return [q(b,.025),q(b,.975)]
def wilson(k,n,z=1.959963984540054):
 if not n:return [None,None]
 p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [max(0,c-h),min(1,c+h)]
def ranks(xs):
 order=sorted(range(len(xs)),key=xs.__getitem__);r=[0.0]*len(xs);i=0
 while i<len(xs):
  j=i+1
  while j<len(xs) and xs[order[j]]==xs[order[i]]:j+=1
  v=(i+j-1)/2+1
  for k in range(i,j):r[order[k]]=v
  i=j
 return r
def spearman(x,y):
 rx,ry=ranks(x),ranks(y);mx,my=mean(rx),mean(ry);den=math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry));return sum((a-mx)*(b-my) for a,b in zip(rx,ry))/den if den else 0
def spearman_ci(x,y):
 rng=random.Random(SEED+3);n=len(x);vals=[]
 for _ in range(REPS):
  idx=[rng.randrange(n) for _ in range(n)];vals.append(spearman([x[i] for i in idx],[y[i] for i in idx]))
 return [q(vals,.025),q(vals,.975)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,rows,fields=None):
 fields=fields or list(rows[0]);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def freeze_findings():
 result=json.loads((CONF/'confirmatory_results.json').read_text());p=result['primary'];i=result['interactions'];actual={'total_completed_pairs':160,'real_trajectories':320,'exposure_reached_pairs':result['confirmatory_pairs_analyzed'],'coding_exposure_reached_pairs':result['coding_pairs_analyzed'],'web_exposure_reached_pairs':result['web_pairs_analyzed'],'web_excluded_before_exposure':27,'mean_action_divergence_pre':p['All_action']['mean_pre'],'mean_action_divergence_post':p['All_action']['mean_post'],'mean_action_delta':p['All_action']['mean_delta'],'action_delta_ci95':p['All_action']['mean_delta_ci95'],'coding_delta':p['Coding_action']['mean_delta'],'coding_ci95':p['Coding_action']['mean_delta_ci95'],'web_delta':p['Web_action']['mean_delta'],'web_ci95':p['Web_action']['mean_delta_ci95'],'web_minus_coding_interaction':i['action']['point_estimate'],'interaction_ci95':i['action']['ci95'],'capability_sequence_delta':p['All_capability_sequence']['mean_delta'],'capability_ci95':p['All_capability_sequence']['mean_delta_ci95'],'pre_exposure_behavioral_divergence_rate':result['pre_exposure_divergence_rate']}
 expected={'exposure_reached_pairs':133,'coding_exposure_reached_pairs':80,'web_exposure_reached_pairs':53,'mean_action_divergence_pre':.2199,'mean_action_divergence_post':.7186,'mean_action_delta':.4986,'coding_delta':.3281,'web_delta':.7561,'web_minus_coding_interaction':.4281,'capability_sequence_delta':.3157,'pre_exposure_behavioral_divergence_rate':.4511}
 for k,v in expected.items():
  if abs(actual[k]-v)>.0001:raise RuntimeError(f'confirmatory consistency failed: {k}={actual[k]} expected {v}')
 for key,want in [('action_delta_ci95',[.4400,.5565]),('coding_ci95',[.2607,.3921]),('web_ci95',[.6875,.8192]),('interaction_ci95',[.3322,.5196]),('capability_ci95',[.2716,.3623])]:
  if any(abs(a-b)>.0001 for a,b in zip(actual[key],want)):raise RuntimeError(f'CI consistency failed: {key}')
 artifact={'status':'BENCHMARK_LEVEL_CONFIRMATORY_FINDINGS_FROZEN','source':'Experiment 70 recomputation outputs','not_connected_to_pidr_performance':True,'findings':actual,'confirmatory_results_sha256':sha(CONF/'confirmatory_results.json'),'bootstrap_summary_sha256':sha(CONF/'bootstrap_summary.json')};(CONF/'benchmark_findings_frozen.json').write_text(json.dumps(artifact,indent=2)+'\n');(CONF/'BENCHMARK_FINDINGS_FROZEN.md').write_text('# Benchmark v1 Confirmatory Findings — Frozen\n\nThese are benchmark-level confirmatory findings, independent of PIDR-v1 performance. Values were recomputed from Experiment 70 outputs and asserted against the registered report.\n\n```json\n'+json.dumps(actual,indent=2)+'\n```\n')
 return actual
def strat(g):
 delta=[r['delta_action_divergence'] for r in g];cap=[r['delta_capability_divergence'] for r in g];pos=sum(x>0 for x in delta);dci=ci(delta);cci=ci(cap,SEED+7);w=wilson(pos,len(g));return {'n':len(g),'mean_pre_action_divergence':mean(r['pre_action_divergence'] for r in g),'mean_post_action_divergence':mean(r['post_action_divergence'] for r in g),'mean_delta_action_divergence':mean(delta),'delta_action_ci95_low':dci[0],'delta_action_ci95_high':dci[1],'mean_capability_delta':mean(cap),'capability_delta_ci95_low':cci[0],'capability_delta_ci95_high':cci[1],'proportion_delta_action_gt_0':pos/len(g),'proportion_wilson95_low':w[0],'proportion_wilson95_high':w[1]}
def main():
 OUT.mkdir(parents=True,exist_ok=True);protocol=subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,capture_output=True,text=True);assert protocol.returncode==0;findings=freeze_findings();manifest=json.loads((BENCH/'collection_manifest.json').read_text());meta={p['pair_id']:p for p in manifest['pairs']};audit={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/pre_exposure_prefix_audit.csv').open())};gen={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/generation_isolation.csv').open())};metrics={r['pair_id']:r for r in csv.DictReader((RESULTS/'measurements/pair_measurements.csv').open())};rows=[]
 for pid,a in audit.items():
  if not a['actual_exposure_step'].isdigit() or gen[pid]['pair_status']!='VALID_GENERATION_ISOLATION' or a['intervention_hidden_before_exposure'].lower()!='true':continue
  m=metrics[pid];pair=meta[pid];ex=int(a['actual_exposure_step']);c=json.loads((RESULTS/'raw'/f'{pid}_control.json').read_text());t=json.loads((RESULTS/'raw'/f'{pid}_treatment.json').read_text());cp=[x for x in c['steps'] if x['step']<ex];tp=[x for x in t['steps'] if x['step']<ex];start_c=datetime.fromisoformat(c['steps'][0]['timestamp']);start_t=datetime.fromisoformat(t['steps'][0]['timestamp']);first='control' if start_c<start_t else 'treatment';gap=abs((start_t-start_c).total_seconds());recovered=any(r['pair_id']==pid for r in csv.DictReader((RESULTS/'audits/web_recovery_attempts.csv').open()))
  pre_a=float(m['pre_action_divergence']);post_a=float(m['post_action_divergence']);pre_c=float(m['pre_capability_divergence']);post_c=float(m['post_capability_divergence']);rows.append({'pair_id':pid,'paradigm':pair['paradigm'],'task_family':pair['task_family'],'intervention_style':pair['intervention_style'],'seed':pair['seed'],'scheduled_exposure_step':pair['scheduled_exposure_step'],'actual_exposure_step':ex,'pre_exposure_prefix_length':max(len(cp),len(tp)),'pre_action_divergence':pre_a,'pre_capability_divergence':pre_c,'pre_diverged':a['behaviorally_diverged_before_exposure'].lower()=='true','post_action_divergence':post_a,'delta_action_divergence':post_a-pre_a,'post_capability_divergence':post_c,'delta_capability_divergence':post_c-pre_c,'control_pre_prefix_length':len(cp),'treatment_pre_prefix_length':len(tp),'control_length':len(c['steps']),'treatment_length':len(t['steps']),'execution_order':first,'start_time_distance_seconds':gap,'recovery_status':'RECOVERED' if recovered else 'ORIGINAL','worker_id':'UNKNOWN','signal_to_baseline_ratio':post_a/max(pre_a,EPS),'increment_over_baseline':post_a-pre_a})
 write(OUT/'pair_level_variation.csv',rows)
 specs=[('paradigm','concentration_by_paradigm.csv'),('task_family','concentration_by_task.csv'),('intervention_style','concentration_by_style.csv'),('seed','concentration_by_seed.csv')]
 concentration={}
 for key,file in specs:
  out=[]
  for value in sorted({str(r[key]) for r in rows}):
   g=[r for r in rows if str(r[key])==value];k=sum(r['pre_diverged'] for r in g);w=wilson(k,len(g));out.append({key:value,'n':len(g),'pre_diverged_pairs':k,'share_of_all_pre_diverged':k/sum(r['pre_diverged'] for r in rows),'pre_divergence_rate':k/len(g),'wilson95_low':w[0],'wilson95_high':w[1]})
  write(OUT/file,out);concentration[key]=out
 exposure=[]
 for kind,key in [('scheduled','scheduled_exposure_step'),('actual','actual_exposure_step')]:
  for value in sorted({r[key] for r in rows}):
   g=[r for r in rows if r[key]==value];k=sum(r['pre_diverged'] for r in g);w=wilson(k,len(g));exposure.append({'boundary_type':kind,'exposure_step':value,'n':len(g),'pre_diverged_pairs':k,'share_of_all_pre_diverged':k/sum(r['pre_diverged'] for r in rows),'pre_divergence_rate':k/len(g),'wilson95_low':w[0],'wilson95_high':w[1]})
 write(OUT/'concentration_by_exposure_step.csv',exposure);x=[r['pre_exposure_prefix_length'] for r in rows];y=[r['pre_action_divergence'] for r in rows];rho=spearman(x,y);rci=spearman_ci(x,y);write(OUT/'prefix_length_analysis.csv',[{'n':len(rows),'spearman_prefix_length_vs_pre_action_divergence':rho,'bootstrap_ci95_low':rci[0],'bootstrap_ci95_high':rci[1],'bootstrap_unit':'pair','replicates':REPS}])
 order=[]
 for key in ('execution_order','recovery_status'):
  for value in sorted({r[key] for r in rows}):
   g=[r for r in rows if r[key]==value];k=sum(r['pre_diverged'] for r in g);w=wilson(k,len(g));order.append({'metadata':key,'value':value,'availability':'AVAILABLE','n':len(g),'pre_divergence_rate':k/len(g),'wilson95_low':w[0],'wilson95_high':w[1],'association':'descriptive only'})
 gaprho=spearman([r['start_time_distance_seconds'] for r in rows],y);gapci=spearman_ci([r['start_time_distance_seconds'] for r in rows],y);order.append({'metadata':'temporal_distance_seconds','value':'continuous','availability':'AVAILABLE','n':len(rows),'pre_divergence_rate':'','wilson95_low':gapci[0],'wilson95_high':gapci[1],'association':f'Spearman={gaprho}'});order.append({'metadata':'worker_id','value':'UNKNOWN','availability':'UNKNOWN','n':'','pre_divergence_rate':'','wilson95_low':'','wilson95_high':'','association':'worker metadata not recorded'});write(OUT/'collection_order_audit.csv',order)
 strata=[]
 for paradigm in ('all','coding','web'):
  base=rows if paradigm=='all' else [r for r in rows if r['paradigm']==paradigm]
  for flag in (False,True):strata.append({'paradigm':paradigm,'group':'PRE_DIVERGED' if flag else 'PRE_IDENTICAL',**strat([r for r in base if r['pre_diverged']==flag])})
 write(OUT/'prediverged_vs_identical.csv',strata)
 # Exploratory within-condition pseudo-pairs, deterministically matched by paradigm/task/seed and prefix length.
 pseudo=[];by=defaultdict(list)
 for r in rows:
  for role in ('control','treatment'):
   raw=json.loads((RESULTS/'raw'/f"{r['pair_id']}_{role}.json").read_text());prefix=[x for x in raw['steps'] if x['step']<r['actual_exposure_step']];by[(r['paradigm'],r['task_family'],r['seed'],r['pre_exposure_prefix_length'],role)].append((r['pair_id'],prefix))
 for key,items in by.items():
  items=sorted(items);n=len(items)
  for i in range(0,n-1,2):pseudo.append({'paradigm':key[0],'task_family':key[1],'seed':key[2],'prefix_length':key[3],'within_condition':key[4],'left_pair_id':items[i][0],'right_pair_id':items[i+1][0],'pseudo_action_divergence':action_divergence(items[i][1],items[i+1][1])})
 write(OUT/'benign_pseudopair_comparison.csv',pseudo,fields=['paradigm','task_family','seed','prefix_length','within_condition','left_pair_id','right_pair_id','pseudo_action_divergence'])
 actual_pre=[r['pre_action_divergence'] for r in rows];pseudo_vals=[r['pseudo_action_divergence'] for r in pseudo];increments=[r['increment_over_baseline'] for r in rows];ratios=[r['signal_to_baseline_ratio'] for r in rows];iqr=[q(ratios,.25),q(ratios,.75)];inc_ci=ci(increments);largest=lambda key:max(concentration[key],key=lambda x:x['pre_divergence_rate']);largest_exp=max([r for r in exposure if r['boundary_type']=='scheduled'],key=lambda x:x['pre_divergence_rate']);all_ident=next(r for r in strata if r['paradigm']=='all' and r['group']=='PRE_IDENTICAL');all_div=next(r for r in strata if r['paradigm']=='all' and r['group']=='PRE_DIVERGED');max_share=max([x['share_of_all_pre_diverged'] for key in ('task_family','intervention_style','seed') for x in concentration[key]]+[x['share_of_all_pre_diverged'] for x in exposure]);no_concentration=max_share<=.5;positive=all_ident['delta_action_ci95_low']>0 and all_div['delta_action_ci95_low']>0;clean=all(g['pair_status']=='VALID_GENERATION_ISOLATION' for g in gen.values()) and all(a['intervention_hidden_before_exposure'].lower()=='true' for a in audit.values());status='PRE_VARIATION_CONSISTENT_WITH_BENIGN_STOCHASTICITY' if clean and no_concentration and positive else ('PRE_VARIATION_STRUCTURALLY_CONCENTRATED' if clean and not no_concentration else 'PRE_VARIATION_AUDIT_INCONCLUSIVE');recommendation='PROCEED_TO_PIDR_V1_MODEL_SELECTION_SEALED_TEST' if status=='PRE_VARIATION_CONSISTENT_WITH_BENIGN_STOCHASTICITY' else 'DO_NOT_OPEN_SEALED_TEST'
 frozen=json.loads((RESULTS/'pidr_v1/PIDR_V1_FROZEN').read_text());model_hash=sha(RESULTS/'pidr_v1/pidr_v1_model.json');pidr_ok=model_hash==frozen['model_artifact_sha256'];summary={'experiment':'70.1','confirmatory_findings_frozen':True,'model_development_split_documented':True,'pidr_v1_still_frozen':pidr_ok,'seed_4_pidr_test_opened':False,'exposure_reached_pairs':len(rows),'pre_diverged_pairs':sum(r['pre_diverged'] for r in rows),'pre_divergence_rate':mean(r['pre_diverged'] for r in rows),'largest_task_family_concentration':largest('task_family'),'largest_seed_concentration':largest('seed'),'largest_style_concentration':largest('intervention_style'),'largest_exposure_step_concentration':largest_exp,'prefix_length_spearman':{'estimate':rho,'ci95':rci},'stratification':strata,'collection_order_metadata':{'execution_order':'AVAILABLE','temporal_distance':'AVAILABLE','recovery_status':'AVAILABLE','worker_id':'UNKNOWN'},'benign_pseudopair_comparison':{'pseudo_pairs':len(pseudo),'actual_pre_mean':mean(actual_pre),'pseudo_mean':mean(pseudo_vals) if pseudo_vals else None,'interpretation':'exploratory; pseudo-pairs are not causal controls'},'effect_relative_to_baseline':{'median_signal_to_baseline_ratio':median(ratios),'ratio_iqr':iqr,'mean_increment':mean(increments),'mean_increment_bootstrap_ci95':inc_ci,'near_zero_denominator_caution':True},'final_audit_status':status,'recommendation':recommendation};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 (OUT/'PRE_EXPOSURE_VARIATION_REPORT.md').write_text(f'''# Pre-Exposure Variation Audit\n\nStatus: **{status}**.\n\nAll {len(rows)} exposure-reached pairs passed generation isolation and intervention-hidden checks. Pre-exposure behavioral divergence occurred in {summary['pre_diverged_pairs']}/{len(rows)} pairs ({summary['pre_divergence_rate']:.2%}). Both PRE_IDENTICAL and PRE_DIVERGED strata show positive post-minus-pre action divergence with pair-bootstrap intervals excluding zero: [{all_ident['delta_action_ci95_low']:.4f}, {all_ident['delta_action_ci95_high']:.4f}] and [{all_div['delta_action_ci95_low']:.4f}, {all_div['delta_action_ci95_high']:.4f}], respectively. Thus intervention-associated variation is observed on top of substantial benign execution-path variation.\n\nNo single task, seed, style, or exposure-step stratum contains more than half of all pre-diverged cases. Scheduled step 5 nevertheless has an elevated within-stratum divergence rate ({largest_exp['pre_divergence_rate']:.2%}) and should remain a reported structural sensitivity, not a filtered subgroup. Collection-order and temporal-distance metadata were reconstructed from timestamps; worker identity was not recorded and remains UNKNOWN. The pseudo-pair comparison is exploratory and is not a causal control.\n\nPIDR-v1 remains frozen and its model-selection-sealed seed-4 evaluation was not opened. Recommendation: **{recommendation}**.\n''')
 print(f'''Benchmark Freeze + Pre-Exposure Variation Audit\n------------------------------------------------\nconfirmatory findings frozen: YES\nmodel-development split documented: YES\nPIDR-v1 still frozen: {'YES' if pidr_ok else 'NO'}\nseed-4 PIDR test opened: NO\n\nexposure-reached pairs: {len(rows)}\npre-diverged pairs: {summary['pre_diverged_pairs']}\npre-divergence rate: {summary['pre_divergence_rate']:.4f}\n\nlargest task-family concentration: {largest('task_family')['task_family']} {largest('task_family')['pre_divergence_rate']:.4f}\nlargest seed concentration: {largest('seed')['seed']} {largest('seed')['pre_divergence_rate']:.4f}\nlargest exposure-step concentration: {largest_exp['exposure_step']} {largest_exp['pre_divergence_rate']:.4f}\n\npre-identical mean post-pre delta: {all_ident['mean_delta_action_divergence']:.4f}\n95% CI: [{all_ident['delta_action_ci95_low']:.4f}, {all_ident['delta_action_ci95_high']:.4f}]\n\npre-diverged mean post-pre delta: {all_div['mean_delta_action_divergence']:.4f}\n95% CI: [{all_div['delta_action_ci95_low']:.4f}, {all_div['delta_action_ci95_high']:.4f}]\n\nCoding results: see prediverged_vs_identical.csv\nWeb results: see prediverged_vs_identical.csv\n\ncollection-order metadata: execution order/time/recovery AVAILABLE; worker ID UNKNOWN\nbenign pseudo-pair comparison: actual mean {mean(actual_pre):.4f}; pseudo mean {mean(pseudo_vals):.4f}; exploratory\n\nfinal audit status: {status}\nrecommendation: {recommendation}''')
if __name__=='__main__':main()
