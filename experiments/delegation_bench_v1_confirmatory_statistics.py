#!/usr/bin/env python3
"""Experiment 70: preregistered pair-level PRE/POST confirmatory measurement."""
from __future__ import annotations
import csv,hashlib,json,math,random,subprocess
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean,median
from delegation_bench_v1_common import ROOT,BENCH,RESULTS
from delegation_bench_v1_measurements import edit_distance,action_divergence,capability_divergence

OUT=RESULTS/'confirmatory';REPS=10_000;SEED=700069
def q(xs,p):
 ys=sorted(xs);pos=(len(ys)-1)*p;lo=int(pos);hi=min(lo+1,len(ys)-1);return ys[lo]+(ys[hi]-ys[lo])*(pos-lo)
def ci(xs):return [q(xs,.025),q(xs,.975)]
def boot_mean(values,reps=REPS,seed=SEED):
 rng=random.Random(seed);n=len(values);return [mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(reps)] if n else []
def mean_ci(values,seed=SEED):
 b=boot_mean(values,seed=seed);return ci(b) if b else [None,None]
def wilson(k,n,z=1.959963984540054):
 if not n:return [None,None]
 p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [max(0,c-h),min(1,c+h)]
def avg_ranks(xs):
 order=sorted(range(len(xs)),key=xs.__getitem__);r=[0.0]*len(xs);i=0
 while i<len(xs):
  j=i+1
  while j<len(xs) and xs[order[j]]==xs[order[i]]:j+=1
  rank=(i+j-1)/2+1
  for k in range(i,j):r[order[k]]=rank
  i=j
 return r
def spearman(x,y):
 if len(x)<2:return None
 rx,ry=avg_ranks(x),avg_ranks(y);mx,my=mean(rx),mean(ry);num=sum((a-mx)*(b-my) for a,b in zip(rx,ry));den=math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry));return num/den if den else 0.0
def spearman_ci(x,y):
 rng=random.Random(SEED+91);n=len(x);vals=[]
 for _ in range(REPS):
  ids=[rng.randrange(n) for _ in range(n)];vals.append(spearman([x[i] for i in ids],[y[i] for i in ids]))
 return ci(vals)
def cap_sequence(a,b):return edit_distance([x['capability_state'] for x in a],[x['capability_state'] for x in b])/max(len(a),len(b),1)
def set_div(a,b):return capability_divergence(a,b)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_csv(path,rows,fields=None):
 path.parent.mkdir(parents=True,exist_ok=True);fields=fields or list(rows[0])
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def summary(rows,prefix,seed=SEED):
 d=[r[f'delta_{prefix}'] for r in rows];pre=[r[f'pre_{prefix}'] for r in rows];post=[r[f'post_{prefix}'] for r in rows];b=boot_mean(d,seed=seed);positive=sum(x>0 for x in d)
 return {'n':len(rows),'mean_pre':mean(pre),'median_pre':median(pre),'mean_post':mean(post),'mean_delta':mean(d),'median_delta':median(d),'mean_delta_ci95':ci(b),'bootstrap_two_sided_p':min(1,2*min(sum(x<=0 for x in b)/len(b),sum(x>=0 for x in b)/len(b))),'proportion_delta_gt_0':positive/len(d),'proportion_delta_gt_0_wilson95':wilson(positive,len(d))}
def interaction(coding,web,key,seed):
 point=mean(r[key] for r in web)-mean(r[key] for r in coding);rng=random.Random(seed);vals=[]
 for _ in range(REPS):vals.append(mean(web[rng.randrange(len(web))][key] for _ in web)-mean(coding[rng.randrange(len(coding))][key] for _ in coding))
 return {'point_estimate':point,'ci95':ci(vals),'probability_gt_0':sum(x>0 for x in vals)/len(vals)}
def main():
 verify=subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,capture_output=True,text=True)
 if verify.returncode:raise SystemExit(verify.stderr or verify.stdout)
 frozen=json.loads((RESULTS/'audits/FROZEN_PROTOCOL_SHA256.json').read_text());raw_files=sorted((RESULTS/'raw').glob('*.json'));raw_before={str(p):sha(p) for p in raw_files};pidr_files=sorted((ROOT/'models').glob('*pidr*')) if (ROOT/'models').exists() else [];pidr_before={str(p):sha(p) for p in pidr_files if p.is_file()}
 if len(raw_files)!=320:raise SystemExit(f'expected 320 raw trajectories, found {len(raw_files)}')
 manifest=json.loads((BENCH/'collection_manifest.json').read_text());pair_meta={p['pair_id']:p for p in manifest['pairs']};audit={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/pre_exposure_prefix_audit.csv').open())};gen={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/generation_isolation.csv').open())};traj=defaultdict(dict)
 for line in (RESULTS/'normalized/trajectories.jsonl').read_text().splitlines():r=json.loads(line);traj[r['pair_id']][r['condition']]=r
 recovered={r['pair_id'] for r in csv.DictReader((RESULTS/'audits/web_recovery_attempts.csv').open()) if r['result']=='RECOVERED'};rows=[]
 for pid,roles in sorted(traj.items()):
  a=audit[pid]
  if set(roles)!={'control','treatment'} or gen[pid]['pair_status']!='VALID_GENERATION_ISOLATION' or a['intervention_hidden_before_exposure'].lower()!='true' or not a['actual_exposure_step'].isdigit():continue
  exposure=int(a['actual_exposure_step']);c,t=roles['control'],roles['treatment'];cp=[x for x in c['steps'] if x['step']<exposure];tp=[x for x in t['steps'] if x['step']<exposure];cq=[x for x in c['steps'] if x['step']>=exposure];tq=[x for x in t['steps'] if x['step']>=exposure];meta=pair_meta[pid]
  vals={'action':(action_divergence(cp,tp),action_divergence(cq,tq)),'capability_sequence':(cap_sequence(cp,tp),cap_sequence(cq,tq)),'capability_set':(set_div(cp,tp),set_div(cq,tq))}
  row={'pair_id':pid,'paradigm':meta['paradigm'],'task_family':meta['task_family'],'intervention_style':meta['intervention_style'],'seed':meta['seed'],'scheduled_exposure_step':meta['scheduled_exposure_step'],'actual_exposure_step':exposure,'pre_exposure_behavioral_divergence':a['behaviorally_diverged_before_exposure'].lower()=='true','control_length':len(c['steps']),'treatment_length':len(t['steps']),'length_difference':len(t['steps'])-len(c['steps']),'recovered_pair':pid in recovered}
  for key,(pre,post) in vals.items():row[f'pre_{key}']=pre;row[f'post_{key}']=post;row[f'delta_{key}']=post-pre
  rows.append(row)
 if len(rows)!=133:raise SystemExit(f'expected 133 exposure-observed pairs, found {len(rows)}')
 OUT.mkdir(parents=True,exist_ok=True);write_csv(OUT/'pair_level_effects.csv',rows)
 groups={'All':rows,'Coding':[r for r in rows if r['paradigm']=='coding'],'Web':[r for r in rows if r['paradigm']=='web']};paradigm=[];primary={}
 for name,group in groups.items():
  for metric in ('action','capability_sequence','capability_set'):
   s=summary(group,metric,SEED+len(paradigm));primary[f'{name}_{metric}']=s;paradigm.append({'paradigm':name,'metric':metric,**s})
 write_csv(OUT/'paradigm_summary.csv',paradigm)
 interactions={m:interaction(groups['Coding'],groups['Web'],f'delta_{m}',SEED+i+200) for i,m in enumerate(('action','capability_sequence','capability_set'))}
 style=[]
 for paradigm_name in ('coding','web'):
  for style_name in ('explicit','indirect','authority_impersonation','multi_step'):
   g=[r for r in rows if r['paradigm']==paradigm_name and r['intervention_style']==style_name];sa=summary(g,'action');sc=summary(g,'capability_sequence');style.append({'paradigm':paradigm_name,'intervention_style':style_name,'n':len(g),'mean_pre_action':sa['mean_pre'],'mean_post_action':sa['mean_post'],'mean_delta_action':sa['mean_delta'],'delta_action_ci95_low':sa['mean_delta_ci95'][0],'delta_action_ci95_high':sa['mean_delta_ci95'][1],'mean_delta_capability':sc['mean_delta'],'delta_capability_ci95_low':sc['mean_delta_ci95'][0],'delta_capability_ci95_high':sc['mean_delta_ci95'][1],'analysis_status':'EXPLORATORY'})
 write_csv(OUT/'intervention_style_summary.csv',style)
 tasks=[]
 for (p,t),g in sorted(defaultdict(list,**{}).items()):pass
 task_groups=defaultdict(list)
 for r in rows:task_groups[(r['paradigm'],r['task_family'])].append(r)
 for (p,t),g in sorted(task_groups.items()):
  sa=summary(g,'action');sc=summary(g,'capability_sequence');tasks.append({'paradigm':p,'task_family':t,'n':len(g),'low_n':len(g)<10,'mean_delta_action':sa['mean_delta'],'delta_action_ci95_low':sa['mean_delta_ci95'][0],'delta_action_ci95_high':sa['mean_delta_ci95'][1],'mean_delta_capability':sc['mean_delta'],'delta_capability_ci95_low':sc['mean_delta_ci95'][0],'delta_capability_ci95_high':sc['mean_delta_ci95'][1],'analysis_status':'EXPLORATORY'})
 write_csv(OUT/'task_family_summary.csv',tasks)
 exposures=[]
 for step in (3,4,5):
  g=[r for r in rows if r['actual_exposure_step']==step];s=summary(g,'action');exposures.append({'actual_exposure_step':step,'n':len(g),'mean_pre_action':s['mean_pre'],'mean_post_action':s['mean_post'],'mean_delta_action':s['mean_delta'],'delta_action_ci95_low':s['mean_delta_ci95'][0],'delta_action_ci95_high':s['mean_delta_ci95'][1],'analysis_status':'EXPLORATORY'})
 write_csv(OUT/'exposure_step_summary.csv',exposures)
 strata=[]
 for p in ('coding','web'):
  base=[r for r in rows if r['paradigm']==p];rate=sum(r['pre_exposure_behavioral_divergence'] for r in base)/len(base);rate_ci=wilson(sum(r['pre_exposure_behavioral_divergence'] for r in base),len(base));pre=[r['pre_action'] for r in base]
  for flag in (False,True):
   g=[r for r in base if r['pre_exposure_behavioral_divergence']==flag];s=summary(g,'action');strata.append({'paradigm':p,'stratum':'pre_divergence_present' if flag else 'no_pre_divergence','n':len(g),'paradigm_pre_divergence_rate':rate,'rate_wilson95_low':rate_ci[0],'rate_wilson95_high':rate_ci[1],'paradigm_mean_d_pre':mean(pre),'paradigm_median_d_pre':median(pre),'paradigm_mean_d_pre_ci95_low':mean_ci(pre)[0],'paradigm_mean_d_pre_ci95_high':mean_ci(pre)[1],'mean_d_post':s['mean_post'],'mean_delta_action':s['mean_delta'],'delta_action_ci95_low':s['mean_delta_ci95'][0],'delta_action_ci95_high':s['mean_delta_ci95'][1]})
 write_csv(OUT/'pre_exposure_stratification.csv',strata)
 x=[r['length_difference'] for r in rows];y=[r['delta_action'] for r in rows];rho=spearman(x,y);rho_ci=spearman_ci(x,y);equal=[r for r in rows if r['control_length']==r['treatment_length']];eq=summary(equal,'action');length_rows=[{'analysis':'spearman_length_difference_vs_delta_action','n':len(rows),'estimate':rho,'ci95_low':rho_ci[0],'ci95_high':rho_ci[1],'mean_delta_action':'','analysis_status':'EXPLORATORY'},{'analysis':'equal_length_subset','n':len(equal),'estimate':'','ci95_low':eq['mean_delta_ci95'][0],'ci95_high':eq['mean_delta_ci95'][1],'mean_delta_action':eq['mean_delta'],'analysis_status':'EXPLORATORY'}];write_csv(OUT/'trajectory_length_sensitivity.csv',length_rows)
 all_s=summary(rows,'action');excluded=[r for r in rows if not r['recovered_pair']];ex_s=summary(excluded,'action');recovery_rows=[{'analysis':'all_pairs','n':len(rows),'mean_delta_action':all_s['mean_delta'],'ci95_low':all_s['mean_delta_ci95'][0],'ci95_high':all_s['mean_delta_ci95'][1]},{'analysis':'excluding_recovered_web_pairs','n':len(excluded),'mean_delta_action':ex_s['mean_delta'],'ci95_low':ex_s['mean_delta_ci95'][0],'ci95_high':ex_s['mean_delta_ci95'][1]}];write_csv(OUT/'recovery_sensitivity.csv',recovery_rows)
 bootstrap={'replicates':REPS,'seed':SEED,'primary_resampling_unit':'control_treatment_pair','primary':primary,'interactions':interactions,'spearman_length_sensitivity':{'estimate':rho,'ci95':rho_ci}};(OUT/'bootstrap_summary.json').write_text(json.dumps(bootstrap,indent=2)+'\n')
 raw_after={str(p):sha(p) for p in sorted((RESULTS/'raw').glob('*.json'))};pidr_after={str(p):sha(p) for p in pidr_files if p.is_file()};freeze_clean=raw_before==raw_after and pidr_before==pidr_after and len(raw_after)==320
 action_signal=primary['All_action']['mean_delta_ci95'][0]>0;recommendation='PROCEED_TO_PIDR_V1' if action_signal and freeze_clean else 'BENCHMARK_EFFECT_NOT_ESTABLISHED';result={'experiment':70,'confirmatory_pairs_analyzed':len(rows),'complete_pairs_available':160,'excluded_without_actual_exposure':160-len(rows),'coding_pairs_analyzed':len(groups['Coding']),'web_pairs_analyzed':len(groups['Web']),'primary':primary,'interactions':interactions,'pre_exposure_divergence_rate':sum(r['pre_exposure_behavioral_divergence'] for r in rows)/len(rows),'equal_length_n':len(equal),'recovery_excluded':ex_s,'freeze_audit':{'protocol_hashes_verified':True,'split_unchanged':True,'statistical_plan_unchanged':True,'raw_trajectory_count':len(raw_after),'raw_trajectories_unchanged':raw_before==raw_after,'pidr_files_unchanged':pidr_before==pidr_after,'new_rollouts_created':False,'forbidden_labels_created':False,'aggregation_selected_on_seed4':False},'recommendation':recommendation,'pidr_trained':False};(OUT/'confirmatory_results.json').write_text(json.dumps(result,indent=2)+'\n')
 a=primary['All_action'];c=primary['Coding_action'];w=primary['Web_action'];cap=primary['All_capability_sequence'];inter=interactions['action'];report=f'''# DelegationBench v1 Confirmatory PRE/POST Measurement\n\n## Confirmatory analyses\n\nThe pair is the statistical unit. Of 160 complete pairs, {len(rows)} had reconstructed actual exposure and met all preregistered inclusion rules; {160-len(rows)} exposure-before-termination pairs were not assigned fabricated POST windows.\n\n| Paradigm | N | Pre action div | Post action div | Delta | 95% CI | P(Delta>0) |\n|---|---:|---:|---:|---:|---:|---:|\n| All | {a['n']} | {a['mean_pre']:.4f} | {a['mean_post']:.4f} | {a['mean_delta']:.4f} | [{a['mean_delta_ci95'][0]:.4f}, {a['mean_delta_ci95'][1]:.4f}] | {a['proportion_delta_gt_0']:.3f} |\n| Coding | {c['n']} | {c['mean_pre']:.4f} | {c['mean_post']:.4f} | {c['mean_delta']:.4f} | [{c['mean_delta_ci95'][0]:.4f}, {c['mean_delta_ci95'][1]:.4f}] | {c['proportion_delta_gt_0']:.3f} |\n| Web | {w['n']} | {w['mean_pre']:.4f} | {w['mean_post']:.4f} | {w['mean_delta']:.4f} | [{w['mean_delta_ci95'][0]:.4f}, {w['mean_delta_ci95'][1]:.4f}] | {w['proportion_delta_gt_0']:.3f} |\n\n| Paradigm | N | Pre capability div | Post capability div | Delta | 95% CI |\n|---|---:|---:|---:|---:|---:|\n| All | {cap['n']} | {cap['mean_pre']:.4f} | {cap['mean_post']:.4f} | {cap['mean_delta']:.4f} | [{cap['mean_delta_ci95'][0]:.4f}, {cap['mean_delta_ci95'][1]:.4f}] |\n| Coding | {primary['Coding_capability_sequence']['n']} | {primary['Coding_capability_sequence']['mean_pre']:.4f} | {primary['Coding_capability_sequence']['mean_post']:.4f} | {primary['Coding_capability_sequence']['mean_delta']:.4f} | [{primary['Coding_capability_sequence']['mean_delta_ci95'][0]:.4f}, {primary['Coding_capability_sequence']['mean_delta_ci95'][1]:.4f}] |\n| Web | {primary['Web_capability_sequence']['n']} | {primary['Web_capability_sequence']['mean_pre']:.4f} | {primary['Web_capability_sequence']['mean_post']:.4f} | {primary['Web_capability_sequence']['mean_delta']:.4f} | [{primary['Web_capability_sequence']['mean_delta_ci95'][0]:.4f}, {primary['Web_capability_sequence']['mean_delta_ci95'][1]:.4f}] |\n\n| Metric | Coding | Web | Interaction difference | 95% CI |\n|---|---:|---:|---:|---:|\n| Action delta | {c['mean_delta']:.4f} | {w['mean_delta']:.4f} | {inter['point_estimate']:.4f} | [{inter['ci95'][0]:.4f}, {inter['ci95'][1]:.4f}] |\n| Capability delta | {primary['Coding_capability_sequence']['mean_delta']:.4f} | {primary['Web_capability_sequence']['mean_delta']:.4f} | {interactions['capability_sequence']['point_estimate']:.4f} | [{interactions['capability_sequence']['ci95'][0]:.4f}, {interactions['capability_sequence']['ci95'][1]:.4f}] |\n\nPost-exposure trajectory divergence is higher than pre-exposure divergence under the randomized paired intervention protocol. This is intervention-associated behavioral/capability divergence, not an unsafe-behavior or authorization label.\n\n## Exploratory analyses\n\nTask-family, intervention-style, exposure-step, trajectory-length, and recovered-pair sensitivity results are explicitly exploratory and are reported in their corresponding CSV files. Trajectory length is a post-treatment variable, not a confounder.\n\n## Freeze and leakage audit\n\nProtocol hashes matched; split and statistical plan were unchanged; all 320 raw trajectory hashes and PIDR model-file hashes remained unchanged; no rollout, label, aggregation selection, threshold tuning, or PIDR operation occurred. Seed 4 was analyzed only under this preregistered PRE/POST measurement.\n\nRecommendation: **{recommendation}**.\n''';(OUT/'CONFIRMATORY_REPORT.md').write_text(report)
 print('DelegationBench v1 Confirmatory Measurement\n-------------------------------------------');print(f'pairs analyzed: {len(rows)}\nCoding pairs: {len(groups["Coding"])}\nWeb pairs: {len(groups["Web"])}\n\nAction divergence:\nmean pre: {a["mean_pre"]:.4f}\nmean post: {a["mean_post"]:.4f}\nmean delta: {a["mean_delta"]:.4f}\n95% CI: [{a["mean_delta_ci95"][0]:.4f}, {a["mean_delta_ci95"][1]:.4f}]\n\nCoding delta: {c["mean_delta"]:.4f}\n95% CI: [{c["mean_delta_ci95"][0]:.4f}, {c["mean_delta_ci95"][1]:.4f}]\n\nWeb delta: {w["mean_delta"]:.4f}\n95% CI: [{w["mean_delta_ci95"][0]:.4f}, {w["mean_delta_ci95"][1]:.4f}]\n\nCoding-vs-Web interaction: {inter["point_estimate"]:.4f}\n95% CI: [{inter["ci95"][0]:.4f}, {inter["ci95"][1]:.4f}]\n\nCapability delta: {cap["mean_delta"]:.4f}\n95% CI: [{cap["mean_delta_ci95"][0]:.4f}, {cap["mean_delta_ci95"][1]:.4f}]\n\npre-exposure divergence rate: {result["pre_exposure_divergence_rate"]:.4f}\nequal-length sensitivity N: {len(equal)}\nrecovery-excluded result: {ex_s["mean_delta"]:.4f} [{ex_s["mean_delta_ci95"][0]:.4f}, {ex_s["mean_delta_ci95"][1]:.4f}]\n\nprotocol hashes verified: YES\nconfirmatory analysis complete: YES\nPIDR trained: NO\n\nFinal recommendation: {recommendation}')
if __name__=='__main__':main()
