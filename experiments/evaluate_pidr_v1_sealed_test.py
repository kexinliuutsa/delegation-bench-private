#!/usr/bin/env python3
"""Experiment 72: one-shot frozen PIDR-v1 evaluation on seed 4."""
from __future__ import annotations
import csv,hashlib,json,math,random,subprocess,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));sys.path.insert(0,str(ROOT/'experiments'))
from pidr_v1 import PIDRV1,cosine_distance
from train_pidr_v1 import sample,construct,monotone
from delegation_bench_v1_common import BENCH,RESULTS
OUT=RESULTS/'pidr_v1_sealed_test';PIDR=RESULTS/'pidr_v1';REPS=10_000;SEED=72001
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def quantile(xs,p):
 ys=sorted(xs);x=(len(ys)-1)*p;i=int(x);j=min(i+1,len(ys)-1);return ys[i]+(ys[j]-ys[i])*(x-i)
def ci(xs):return [quantile(xs,.025),quantile(xs,.975)]
def wilson(k,n,z=1.959963984540054):
 if not n:return [None,None]
 p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [max(0,c-h),min(1,c+h)]
def auc(control,treatment):
 if not control or not treatment:return None
 return sum((t>c)+.5*(t==c) for c in control for t in treatment)/(len(control)*len(treatment))
def write(path,rows,fields=None):
 fields=fields or list(rows[0]);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def preflight():
 if (OUT/'SEALED_TEST_OPENED').exists():raise SystemExit('SEALED_TEST_OPENED already exists; refusing recomputation')
 frozen=json.loads((PIDR/'PIDR_V1_FROZEN').read_text());checks={'model':sha(PIDR/'pidr_v1_model.json')==frozen['model_artifact_sha256'],'train_script':sha(ROOT/'experiments/train_pidr_v1.py')==frozen['training_script_sha256'],'dev_script':sha(ROOT/'experiments/evaluate_pidr_v1_dev.py')==frozen['evaluation_script_sha256'],'split_policy':(BENCH/'MODEL_DEVELOPMENT_SPLIT_POLICY.md').exists(),'findings_frozen':(RESULTS/'confirmatory/benchmark_findings_frozen.json').exists(),'variation_pass':json.loads((RESULTS/'pre_exposure_variation/summary.json').read_text())['final_audit_status']=='PRE_VARIATION_CONSISTENT_WITH_BENIGN_STOCHASTICITY'};protocol=subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,capture_output=True,text=True);checks['protocol']=protocol.returncode==0
 if not all(checks.values()):raise SystemExit('freeze check failed: '+json.dumps(checks))
 return frozen,checks
def load_jobs(seeds):
 manifest=json.loads((BENCH/'collection_manifest.json').read_text());jobs=[j for j in manifest['jobs'] if j['seed'] in seeds];data=defaultdict(dict)
 for j in jobs:
  raw=json.loads((RESULTS/'raw'/f"{j['pair_id']}_{j['condition']}.json").read_text());data[j['pair_id']][j['condition']]={'job':j,'raw':raw,'samples':[sample(j,raw,i) for i in range(len(raw['steps']))]}
 return data
def geometry(model,data,raw):
 con=construct(data);pre,post,_,matched,early,postn=con;pd=[model.distance(a,b,raw) for a,b in pre];sep=[model.distance(a,b,raw) for a,b in post];mp=[model.distance(a,b,raw) for a,b in matched];samples=[s for roles in data.values() for role in roles.values() for s in role['samples']];var=model.latent_variance(samples) if not raw else PIDRV1(model.latent_dim).latent_variance(samples)
 return {'pre_benign_distance':mean(pd),'post_separation':mean(sep),'separation_alignment_ratio':mean(sep)/max(mean(pd),1e-9),'pre_matched_distance':mean(mp),'post_matched_distance':mean(sep),'post_minus_pre_matched_distance':mean(sep)-mean(mp),'latent_variance':var},con
def monitor_setup(model,train,raw):
 memory=[]
 for roles in train.values():
  xs=roles['control']['samples'];memory.extend((model.encode(a,raw),model.encode(b,raw)) for a,b in zip(xs,xs[1:]))
 def score(s):
  z=model.encode(s,raw);ds=sorted(min(cosine_distance(z,a),cosine_distance(z,b)) for a,b in memory);return mean(ds[:5])
 train_scores=[score(s) for roles in train.values() for s in roles['control']['samples']];threshold=sorted(train_scores)[int(.95*(len(train_scores)-1))];return score,threshold
def evaluate_monitor(model,train,test,raw,subset=None):
 score,threshold=monitor_setup(model,train,raw);records=[]
 for pid,roles in test.items():
  if subset and roles['control']['job']['paradigm']!=subset:continue
  cs=[score(s) for s in roles['control']['samples']];ts=[score(s) for s in roles['treatment']['samples']];c=mean(cs);t=mean(ts);records.append({'pair_id':pid,'paradigm':roles['control']['job']['paradigm'],'control_score':c,'treatment_score':t,'control_alarm':c>threshold,'treatment_alarm':t>threshold,'threshold':threshold})
 controls=[r['control_score'] for r in records];treat=[r['treatment_score'] for r in records];tp=sum(r['treatment_alarm'] for r in records);fp=sum(r['control_alarm'] for r in records);precision=tp/(tp+fp) if tp+fp else None;recall=tp/len(records);f1=2*precision*recall/(precision+recall) if precision is not None and precision+recall else None
 return {'n':len(records),'auroc':auc(controls,treat),'benign_false_alarm':fp/len(records),'pair_detection':recall,'precision':precision,'recall':recall,'f1':f1,'threshold':threshold,'threshold_source':'TRAIN controls only'},records,score
def probe(model,train,test,raw):
 points=[(model.encode(s,raw),s['paradigm']) for roles in train.values() for s in roles['control']['samples']];cent={p:[mean(v) for v in zip(*[z for z,y in points if y==p])] for p in ('coding','web')};correct=total=0
 for roles in test.values():
  for s in roles['control']['samples']:
   z=model.encode(s,raw);pred=min(cent,key=lambda p:sum((a-b)**2 for a,b in zip(z,cent[p])));correct+=pred==s['paradigm'];total+=1
 return correct/total
def bootstrap(test,raw_records,pidr_records,geom_pairs):
 ids=sorted(test);rr={r['pair_id']:r for r in raw_records};pp={r['pair_id']:r for r in pidr_records};rng=random.Random(SEED);out=defaultdict(list)
 for _ in range(REPS):
  sample_ids=[ids[rng.randrange(len(ids))] for _ in ids];r=[rr[x] for x in sample_ids];p=[pp[x] for x in sample_ids];out['auroc_delta'].append(auc([x['control_score'] for x in p],[x['treatment_score'] for x in p])-auc([x['control_score'] for x in r],[x['treatment_score'] for x in r]));out['fa_delta'].append(mean(x['control_alarm'] for x in p)-mean(x['control_alarm'] for x in r));out['detection_delta'].append(mean(x['treatment_alarm'] for x in p)-mean(x['treatment_alarm'] for x in r))
  gp=[geom_pairs[x] for x in sample_ids if x in geom_pairs]
  for key in ('pre','post'):out['geometry_'+key].append(mean(x['pidr_'+key]-x['raw_'+key] for x in gp))
  raw_ratio=mean(x['raw_post'] for x in gp)/max(mean(x['raw_pre'] for x in gp),1e-9);pidr_ratio=mean(x['pidr_post'] for x in gp)/max(mean(x['pidr_pre'] for x in gp),1e-9);out['geometry_ratio'].append(pidr_ratio-raw_ratio)
 return {k:{'point_estimate':mean(v),'ci95':ci(v)} for k,v in out.items()}
def main():
 OUT.mkdir(parents=True,exist_ok=True);frozen,checks=preflight();model_before=sha(PIDR/'pidr_v1_model.json');raw_before={str(p):sha(p) for p in sorted((RESULTS/'raw').glob('*.json'))};intent={'opened_at':datetime.now(timezone.utc).isoformat(),'state':'OPENING_IN_PROGRESS','statement':'Seed 4 model-selection evaluation is now being opened; it may not be treated as sealed again.'};(OUT/'SEALED_TEST_OPENING_IN_PROGRESS').write_text(json.dumps(intent,indent=2)+'\n')
 model=PIDRV1.from_dict(json.loads((PIDR/'pidr_v1_model.json').read_text()));train=load_jobs({0,1,2});test=load_jobs({4});assert len(test)==32 and all(v['control']['job']['seed']==4 for v in test.values());audit={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/pre_exposure_prefix_audit.csv').open())};reached=[pid for pid in test if audit[pid]['actual_exposure_step'].isdigit()];early=[pid for pid in test if pid not in reached];counts={'total_seed4_pairs':len(test),'coding_seed4_pairs':sum(v['control']['job']['paradigm']=='coding' for v in test.values()),'web_seed4_pairs':sum(v['control']['job']['paradigm']=='web' for v in test.values()),'exposure_reached_pairs':len(reached),'early_termination_before_exposure_pairs':len(early),'valid_temporal_analysis_pairs':sum(audit[p]['valid_for_temporal_onset_analysis'].lower()=='true' for p in test)};(OUT/'sealed_test_counts.json').write_text(json.dumps(counts,indent=2)+'\n')
 rawg,rawcon=geometry(model,test,True);pidrg,pidrcon=geometry(model,test,False);write(OUT/'representation_geometry.csv',[{'representation':'Raw',**rawg},{'representation':'PIDR-v1',**pidrg}]);rawprobe=probe(model,train,test,True);pidrprobe=probe(model,train,test,False);write(OUT/'paradigm_probe.csv',[{'representation':'Raw','accuracy':rawprobe,'probe_training':'TRAIN representations only'},{'representation':'PIDR-v1','accuracy':pidrprobe,'probe_training':'TRAIN representations only'}])
 monitor_rows=[];all_records={}
 for rep,raw in [('Raw',True),('PIDR-v1',False)]:
  for group in ('All','coding','web'):
   metric,records,score=evaluate_monitor(model,train,test,raw,None if group=='All' else group);monitor_rows.append({'representation':rep,'subset':group,**metric});
   if group=='All':all_records[rep]=(records,score,metric['threshold'])
 write(OUT/'downstream_monitor.csv',monitor_rows)
 temporal=[]
 for rep in ('Raw','PIDR-v1'):
  records,score,threshold=all_records[rep];by={r['pair_id']:r for r in records}
  for pid in reached:
   roles=test[pid];ex=int(audit[pid]['actual_exposure_step']);pre=[s for s in roles['treatment']['samples'] if s['step']<ex];post=[s for s in roles['treatment']['samples'] if s['step']>=ex];pres=[score(s) for s in pre];posts=[score(s) for s in post];alarm_steps=[s['step'] for s in roles['treatment']['samples'] if score(s)>threshold];first=min(alarm_steps) if alarm_steps else None;temporal.append({'representation':rep,'pair_id':pid,'paradigm':roles['control']['job']['paradigm'],'actual_exposure_step':ex,'pre_exposure_monitor_score':mean(pres) if pres else 0,'post_exposure_monitor_score':mean(posts) if posts else 0,'score_delta':(mean(posts) if posts else 0)-(mean(pres) if pres else 0),'pre_exposure_false_alarm':any(x>threshold for x in pres),'post_exposure_detection':any(x>threshold for x in posts),'first_alarm_relative_to_exposure':first-ex if first is not None else 'NA'})
 write(OUT/'temporal_monitoring.csv',temporal)
 strata=[]
 for flag in (False,True):
  ids={pid for pid in test if audit[pid]['behaviorally_diverged_before_exposure'].lower()==str(flag).lower()};
  for rep in ('Raw','PIDR-v1'):
   records=all_records[rep][0];g=[r for r in records if r['pair_id'] in ids];strata.append({'stratum':'PRE_DIVERGED' if flag else 'PRE_IDENTICAL','representation':rep,'n':len(g),'auroc':auc([x['control_score'] for x in g],[x['treatment_score'] for x in g]),'benign_false_alarm':mean(x['control_alarm'] for x in g),'pair_detection':mean(x['treatment_alarm'] for x in g)})
 write(OUT/'prediverged_stratification.csv',strata)
 # Per-pair geometry contributions for paired bootstrap.
 geom_pairs={}
 for pid in reached:
  roles=test[pid];ex=int(audit[pid]['actual_exposure_step']);cp=[s for s in roles['control']['samples'] if s['step']<ex];tp=[s for s in roles['treatment']['samples'] if s['step']<ex];cq=[s for s in roles['control']['samples'] if s['step']>=ex];tq=[s for s in roles['treatment']['samples'] if s['step']>=ex];pre=monotone(cp,tp);post=monotone(cq,tq)
  if not pre or not post:continue
  rdpre=mean(model.distance(a,b,True) for a,b in pre);pdpre=mean(model.distance(a,b,False) for a,b in pre);rdpost=mean(model.distance(a,b,True) for a,b in post);pdpost=mean(model.distance(a,b,False) for a,b in post);geom_pairs[pid]={'raw_pre':rdpre,'pidr_pre':pdpre,'raw_post':rdpost,'pidr_post':pdpost,'raw_ratio':rdpost/max(rdpre,1e-9),'pidr_ratio':pdpost/max(pdpre,1e-9)}
 boot=bootstrap(test,all_records['Raw'][0],all_records['PIDR-v1'][0],geom_pairs);write(OUT/'bootstrap_comparisons.csv',[{'comparison':k,**v,'ci95_low':v['ci95'][0],'ci95_high':v['ci95'][1]} for k,v in boot.items()],fields=['comparison','point_estimate','ci95','ci95_low','ci95_high'])
 rawmon=next(r for r in monitor_rows if r['representation']=='Raw' and r['subset']=='All');pidrmon=next(r for r in monitor_rows if r['representation']=='PIDR-v1' and r['subset']=='All');hyp={'H1':{'hypothesis':'PIDR-v1 increases post-exposure intervention separation','status':'SUPPORTED' if boot['geometry_post']['ci95'][0]>0 else ('NOT SUPPORTED' if boot['geometry_post']['ci95'][1]<=0 else 'INCONCLUSIVE')},'H2':{'hypothesis':'PIDR-v1 improves separation/alignment ratio','status':'SUPPORTED' if boot['geometry_ratio']['ci95'][0]>0 else ('NOT SUPPORTED' if boot['geometry_ratio']['ci95'][1]<=0 else 'INCONCLUSIVE')},'H3':{'hypothesis':'PIDR-v1 reduces paradigm-specific information','status':'SUPPORTED' if pidrprobe<rawprobe else 'NOT SUPPORTED'},'H4':{'hypothesis':'PIDR-v1 improves frozen-monitor ranking and/or false-alarm behavior','status':'SUPPORTED' if boot['auroc_delta']['ci95'][0]>0 or boot['fa_delta']['ci95'][1]<0 else ('NOT SUPPORTED' if boot['auroc_delta']['ci95'][1]<=0 and boot['fa_delta']['ci95'][0]>=0 else 'INCONCLUSIVE')}};(OUT/'hypothesis_results.json').write_text(json.dumps(hyp,indent=2)+'\n')
 temporal_summary={}
 for rep in ('Raw','PIDR-v1'):
  g=[r for r in temporal if r['representation']==rep];lat=[r['first_alarm_relative_to_exposure'] for r in g if r['first_alarm_relative_to_exposure']!='NA'];temporal_summary[rep]={'pre_exposure_false_alarm_rate':mean(r['pre_exposure_false_alarm'] for r in g),'post_exposure_pair_detection':mean(r['post_exposure_detection'] for r in g),'mean_alarm_latency_relative_to_exposure':mean(lat) if lat else None}
 after=sha(PIDR/'pidr_v1_model.json');raw_after={str(p):sha(p) for p in sorted((RESULTS/'raw').glob('*.json'))};validation={'pidr_sha_unchanged':after==model_before,'no_model_retraining':True,'no_threshold_recalibration':True,'no_aggregation_selection':True,'no_test_label_tuning':True,'no_new_rollouts':raw_before==raw_after,'protocol_unchanged':subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,capture_output=True).returncode==0,'forbidden_labels_added':False,'bootstrap_unit':'pair'};summary={'counts':counts,'geometry':{'Raw':rawg,'PIDR-v1':pidrg},'probe':{'Raw':rawprobe,'PIDR-v1':pidrprobe},'monitor':{'Raw':rawmon,'PIDR-v1':pidrmon},'temporal':temporal_summary,'bootstrap':boot,'hypotheses':hyp,'validation':validation,'status':'PIDR_V1_SEALED_TEST_COMPLETE'};(OUT/'sealed_test_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 report=f'''# PIDR-v1 Model-Selection-Sealed Test\n\nThis is the single frozen seed-4 evaluation. PIDR-v1 and the 5NN diagnostic monitor were not modified or recalibrated.\n\n| Geometry | Raw | PIDR-v1 |\n|---|---:|---:|\n| Pre-benign distance | {rawg['pre_benign_distance']:.4f} | {pidrg['pre_benign_distance']:.4f} |\n| Post separation | {rawg['post_separation']:.4f} | {pidrg['post_separation']:.4f} |\n| Separation/alignment ratio | {rawg['separation_alignment_ratio']:.4f} | {pidrg['separation_alignment_ratio']:.4f} |\n\n| Frozen monitor | Raw | PIDR-v1 |\n|---|---:|---:|\n| AUROC | {rawmon['auroc']:.4f} | {pidrmon['auroc']:.4f} |\n| Benign FA | {rawmon['benign_false_alarm']:.4f} | {pidrmon['benign_false_alarm']:.4f} |\n| Pair detection | {rawmon['pair_detection']:.4f} | {pidrmon['pair_detection']:.4f} |\n\nHypotheses: {json.dumps({k:v['status'] for k,v in hyp.items()})}. PIDR-v1 does not achieve lower absolute pre-benign distance if the table does not show it; no benign-alignment claim is made in that case. No third-paradigm or safety/authority claim is supported.\n''';(OUT/'PIDR_V1_SEALED_TEST_REPORT.md').write_text(report)
 marker={'timestamp':datetime.now(timezone.utc).isoformat(),'pidr_v1_model_sha256':after,'protocol_sha256':sha(RESULTS/'audits/FROZEN_PROTOCOL_SHA256.json'),'exact_seed4_split':{'paradigms':['coding','web'],'seed':4,'pairs':32},'evaluation_script_sha256':sha(__file__),'statement':'This model-selection-sealed test has been opened. PIDR-v1 may not be modified and re-evaluated on the same seed-4 split as if it were still sealed.'};(OUT/'SEALED_TEST_OPENED').write_text(json.dumps(marker,indent=2)+'\n');(OUT/'SEALED_TEST_OPENING_IN_PROGRESS').unlink(missing_ok=True)
 print(f'''PIDR-v1 Model-Selection-Sealed Test\n-----------------------------------\ntest pairs: {counts['total_seed4_pairs']}\nCoding pairs: {counts['coding_seed4_pairs']}\nWeb pairs: {counts['web_seed4_pairs']}\nexposure-reached pairs: {counts['exposure_reached_pairs']}\n\nRepresentation geometry\nRaw pre-benign distance: {rawg['pre_benign_distance']:.4f}\nPIDR pre-benign distance: {pidrg['pre_benign_distance']:.4f}\n\nRaw post separation: {rawg['post_separation']:.4f}\nPIDR post separation: {pidrg['post_separation']:.4f}\n\nRaw ratio: {rawg['separation_alignment_ratio']:.4f}\nPIDR ratio: {pidrg['separation_alignment_ratio']:.4f}\n\nParadigm probe\nRaw accuracy: {rawprobe:.4f}\nPIDR accuracy: {pidrprobe:.4f}\n\nFrozen downstream monitor\nRaw AUROC: {rawmon['auroc']:.4f}\nPIDR AUROC: {pidrmon['auroc']:.4f}\n\nRaw benign FA: {rawmon['benign_false_alarm']:.4f}\nPIDR benign FA: {pidrmon['benign_false_alarm']:.4f}\n\nRaw pair detection: {rawmon['pair_detection']:.4f}\nPIDR pair detection: {pidrmon['pair_detection']:.4f}\n\nPre-diverged stratum: see prediverged_stratification.csv\nPre-identical stratum: see prediverged_stratification.csv\n\nH1: {hyp['H1']['status']}\nH2: {hyp['H2']['status']}\nH3: {hyp['H3']['status']}\nH4: {hyp['H4']['status']}\n\nBootstrap conclusions: see bootstrap_comparisons.csv\n\nPIDR model modified: NO\nThreshold retuned: NO\nSeed-4 sealed test opened: YES\n\nFinal status:\nPIDR_V1_SEALED_TEST_COMPLETE''')
if __name__=='__main__':main()
