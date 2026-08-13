#!/usr/bin/env python3
"""Retrospective published baseline comparison; no rollout or PIDR retraining."""
from __future__ import annotations
import csv,hashlib,json,math,random,statistics,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'experiments'))
from models.pidr_v1 import PIDRV1
from models.deep_coral_delegation import DeepCORALDelegation
from models.mmd_delegation import MMDDelegation
from models.deeplog_delegation import DeepLogDelegation
from train_pidr_v1 import sample,construct,geometry,monitor,auc,monotone
from evaluate_pidr_v1_sealed_test import load_jobs,geometry as eval_geometry,evaluate_monitor,probe
BENCH=ROOT/'benchmarks/delegation_bench_v1';RES=ROOT/'results/delegation_bench_v1';OUT=RES/'published_baselines';REPS=10000
def write(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not rows:path.write_text('');return
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),extrasaction='ignore');w.writeheader();w.writerows(rows)
def event_seq(role):
 out=[]
 for s in role['raw']['steps']:
  cap=s.get('capability_state','A0_OBSERVE');tool=s.get('tool','other');out.append(f'{cap}:{tool}')
 return out
def seq_eval(model,data,threshold):
 c=[];t=[];det=[]
 for r in data.values():
  cs=statistics.mean(model.scores(event_seq(r['control'])));ts=statistics.mean(model.scores(event_seq(r['treatment'])));c.append(cs);t.append(ts);det.append(ts>threshold)
 return {'auroc':auc(c,t),'benign_false_alarm':sum(x>threshold for x in c)/len(c),'pair_detection':sum(det)/len(det)}
def main():
 OUT.mkdir(parents=True,exist_ok=True);raw_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RES/'raw').glob('*.json')};model_path=RES/'pidr_v1/pidr_v1_model.json';pidr_hash=hashlib.sha256(model_path.read_bytes()).hexdigest()
 grid=[{'lambda':x,'latent_dimension':d,'temporal_weight':tw} for x in (.001,.01,.1,1,10,30) for d in (64,128) for tw in (0,.1)]
 methods=[{'method':'PIDR-v1','candidate_count':24,'search_space':'historical Experiment 71','selection_metric':'historical frozen rank aggregation','tie_break_rule':'historical','training_seed':71001,'early_stopping_rule':'fixed 8 epochs','maximum_epochs':8,'optimizer':'deterministic multiplicative projection','learning_rate_policy':'.03 fixed'}]
 methods += [{'method':m,'candidate_count':24,'search_space':grid,'selection_metric':'development separation/alignment ratio subject to latent variance >=0.05','tie_break_rule':'lower paradigm probe, then lower complexity','training_seed':75001,'early_stopping_rule':'fixed 8 epochs','maximum_epochs':8,'optimizer':'deterministic diagonal projection','learning_rate_policy':'.03 fixed'} for m in ('CORAL','MMD')]
 methods += [{'method':'DeepLog','candidate_count':24,'search_space':{'embedding':[16,32],'hidden':[32,64],'history':[3,5,8],'architecture':['GRU-style','LSTM-style']},'selection_metric':'development AUROC','tie_break_rule':'lower complexity','training_seed':75002,'early_stopping_rule':'fixed count-table fit','maximum_epochs':1,'optimizer':'smoothed next-event likelihood','learning_rate_policy':'not applicable'}]
 budget={'status':'FROZEN_BEFORE_TRAINING','experiment_status':'RETROSPECTIVE_PUBLISHED_BASELINE_COMPARISON','methods':methods};(OUT/'HYPERPARAMETER_BUDGET_PROTOCOL.json').write_text(json.dumps(budget,indent=2)+'\n');(OUT/'BASELINE_SELECTION_PROTOCOL.json').write_text(json.dumps({'train_seeds':[0,1,2],'development_seed':3,'existing_evaluation_seed':4,'seed4_used_for_selection':False,'note':'Previously opened evaluation set; retrospective baseline comparison.'},indent=2)+'\n')
 train=load_jobs({0,1,2});dev=load_jobs({3});ev=load_jobs({4});tr=construct(train);dv=construct(dev);pidr=PIDRV1.from_dict(json.loads(model_path.read_text()));devrows=[];selected={}
 # Raw/PIDR frozen rows.
 for name,model,israw in [('RAW',pidr,True),('PIDR-v1',pidr,False)]:
  g=geometry(model,dv,israw);mo=monitor(model,train,dev,israw);devrows.append({'method':name,**g,'paradigm_probe_accuracy':probe(model,train,dev,israw),**{f'monitor_{k}':v for k,v in mo.items() if isinstance(v,(int,float))}})
 for cls,name in [(DeepCORALDelegation,'CORAL'),(MMDDelegation,'MMD')]:
  cand=[]
  coding=[x for pair in tr[0] for x in pair if x['paradigm']=='coding'];web=[x for pair in tr[0] for x in pair if x['paradigm']=='web']
  for i,c in enumerate(grid):
   m=cls(c['latent_dimension'],beta_temp=c['temporal_weight'],seed=75000+i)
   m.fit_alignment(coding,web,epochs=8,lambda_align=c['lambda']);g=geometry(m,dv);mo=monitor(m,train,dev);pr=probe(m,train,dev,False);valid=g['latent_variance']>=.05;cand.append((valid,g['separation_alignment_ratio'],-pr,-c['latent_dimension'],m,c,g,mo,pr))
  best=max(cand,key=lambda x:x[:4]);selected[name]=best[5];model=best[4];g=best[6];mo=best[7];devrows.append({'method':name,**g,'paradigm_probe_accuracy':best[8],**{f'monitor_{k}':v for k,v in mo.items() if isinstance(v,(int,float))}});(OUT/f'{name.lower()}_model.json').write_text(json.dumps({'configuration':best[5],'scales':model.scales},indent=2)+'\n')
 write(OUT/'representation_development_results.csv',devrows)
 models={'RAW':(pidr,True),'CORAL':(DeepCORALDelegation(selected['CORAL']['latent_dimension']),False),'MMD':(MMDDelegation(selected['MMD']['latent_dimension']),False),'PIDR-v1':(pidr,False)}
 for n in ('CORAL','MMD'):models[n][0].scales=json.loads((OUT/f'{n.lower()}_model.json').read_text())['scales']
 evrows=[];records={}
 for name,(m,israw) in models.items():
  g,_=eval_geometry(m,ev,israw);mo,rr,_=evaluate_monitor(m,train,ev,israw);records[name]=rr;evrows.append({'method':name,'evaluation_status':'Previously opened evaluation set; retrospective baseline comparison.',**g,'paradigm_probe_accuracy':probe(m,train,ev,israw),**{f'monitor_{k}':v for k,v in mo.items() if isinstance(v,(int,float))}})
 write(OUT/'representation_existing_evaluation_results.csv',evrows)
 # Pair bootstrap monitor and matched pre/post geometry differences.
 rng=random.Random(75003);ids=sorted(ev);comps=[]
 for a,b in [('CORAL','RAW'),('MMD','RAW'),('PIDR-v1','RAW'),('PIDR-v1','CORAL'),('PIDR-v1','MMD')]:
  ra={x['pair_id']:x for x in records[a]};rb={x['pair_id']:x for x in records[b]};dist=[]
  for _ in range(REPS):
   q=[ids[rng.randrange(len(ids))] for _ in ids];dist.append(auc([ra[x]['control_score'] for x in q],[ra[x]['treatment_score'] for x in q])-auc([rb[x]['control_score'] for x in q],[rb[x]['treatment_score'] for x in q]))
  dist.sort();rowa=next(x for x in evrows if x['method']==a);rowb=next(x for x in evrows if x['method']==b)
  geom=[]
  for pid,roles in ev.items():
   ex=roles['treatment']['raw'].get('actual_exposure_step')
   if ex is None:continue
   cp=[s for s in roles['control']['samples'] if s['step']<ex];tp=[s for s in roles['treatment']['samples'] if s['step']<ex];cq=[s for s in roles['control']['samples'] if s['step']>=ex];tq=[s for s in roles['treatment']['samples'] if s['step']>=ex];pre=monotone(cp,tp);post=monotone(cq,tq)
   if pre and post:geom.append((statistics.mean(models[a][0].distance(x,y,models[a][1]) for x,y in pre)-statistics.mean(models[b][0].distance(x,y,models[b][1]) for x,y in pre),statistics.mean(models[a][0].distance(x,y,models[a][1]) for x,y in post)-statistics.mean(models[b][0].distance(x,y,models[b][1]) for x,y in post)))
  for metric,index in (('pre_benign_distance',0),('post_separation',1)):
   gd=[]
   for _ in range(REPS):gd.append(statistics.mean(geom[rng.randrange(len(geom))][index] for _ in geom))
   gd.sort();comps.append({'comparison':a+' - '+b,'metric':metric,'difference':statistics.mean(gd),'ci95_low':gd[249],'ci95_high':gd[9749],'bootstrap_unit':'pair'})
  comps.append({'comparison':a+' - '+b,'metric':'monitor_auroc','difference':statistics.mean(dist),'ci95_low':dist[249],'ci95_high':dist[9749],'bootstrap_unit':'pair'})
 write(OUT/'representation_bootstrap_comparisons.csv',comps)
 # DeepLog candidates.
 trainseq=[event_seq(r['control']) for r in train.values()];seqdev=[];best=None
 configs=[(e,h,k,a) for e in (16,32) for h in (32,64) for k in (3,5,8) for a in ('GRU','LSTM')][:24]
 for e,h,k,a in configs:
  m=DeepLogDelegation(k,.1,e,h).fit(trainseq);ts=[statistics.mean(m.scores(x)) for x in trainseq];th=sorted(ts)[int(.95*(len(ts)-1))];met=seq_eval(m,dev,th);row={'method':'DeepLog','embedding':e,'hidden':h,'history':k,'architecture':a,**met};seqdev.append(row);key=(met['auroc'],-e-h-k)
  if best is None or key>best[0]:best=(key,m,th,row)
 write(OUT/'sequence_development_results.csv',seqdev);deeplog=best[1];seqev=seq_eval(deeplog,ev,best[2]);legacy=[{'method':'Action frequency','auroc':'MISSING_PROJECT_ARTIFACT','benign_false_alarm':'NA','pair_detection':'NA'},{'method':'Markov','auroc':'MISSING_PROJECT_ARTIFACT','benign_false_alarm':'NA','pair_detection':'NA'},{'method':'Sequence autoencoder','auroc':'MISSING_PROJECT_ARTIFACT','benign_false_alarm':'NA','pair_detection':'NA'},{'method':'DeepLog','evaluation_status':'Previously opened evaluation set; retrospective baseline comparison.',**seqev}];write(OUT/'sequence_existing_evaluation_results.csv',legacy)
 # strata/paradigm from common evaluator.
 strat=[]
 for name,(m,israw) in models.items():
  for par in ('coding','web'):
   mo,_,_=evaluate_monitor(m,train,ev,israw,par);strat.append({'method':name,'stratum_type':'paradigm','stratum':par,**mo})
 write(OUT/'paradigm_stratified_results.csv',strat);write(OUT/'predivergence_stratified_results.csv',[{'status':'diagnostic','source':'results/delegation_bench_v1/pre_exposure_variation/pair_level_variation.csv','note':'Frozen PRE_IDENTICAL/PRE_DIVERGED definitions; method-level re-evaluation unavailable without altering opened evaluation workflow.'}])
 write(OUT/'objective_comparison.csv',[{'method':x,'base_encoder':'PIDR hashed observable-prefix encoder','representation_preservation':x!='RAW','temporal_consistency':x in {'CORAL','MMD','PIDR-v1'},'cross_paradigm_alignment':x in {'CORAL','MMD','PIDR-v1'},'alignment_type':{'RAW':'none','CORAL':'covariance','MMD':'distribution','PIDR-v1':'paired invariance'}[x],'uses_pre_exposure_pairs':x!='RAW','uses_post_exposure_pairs':x=='PIDR-v1','intervention_separation':x=='PIDR-v1','uses_domain_identity_training':x in {'CORAL','MMD'},'uses_treatment_identity_training':x=='PIDR-v1','uses_class_labels':False,'inference_requires_condition':False} for x in ('RAW','CORAL','MMD','PIDR-v1')])
 fair='# Baseline Fairness Audit\n\nAll tunable methods had 24 frozen candidates. CORAL less budget than PIDR: NO. MMD less budget than PIDR: NO. DeepLog less budget than comparable sequence methods: NO (no comparable tuned project artifacts were available). TRAIN examples and seed-3 development selection were shared where applicable; seed 4 was not used for tuning. Parameter counts differ with latent dimension and are recorded in selected artifacts. Fixed 8 epochs were used for alignment methods.\n';(OUT/'BASELINE_FAIRNESS_AUDIT.md').write_text(fair)
 trainreport={'new_rollouts':0,'train_pairs':len(train),'development_pairs':len(dev),'existing_evaluation_pairs':len(ev),'pidr_model_sha256':pidr_hash,'pidr_retrained':False,'candidate_counts':{'PIDR-v1':24,'CORAL':24,'MMD':24,'DeepLog':24},'selected':selected,'deepLog_selected':best[3],'seed4_used_for_tuning':False};(OUT/'training_report.json').write_text(json.dumps(trainreport,indent=2)+'\n')
 # conservative positioning.
 er={x['method']:x for x in evrows};pidr_adv=er['PIDR-v1']['post_separation']>max(er['CORAL']['post_separation'],er['MMD']['post_separation']);position='JOINT_BENCHMARK_REPRESENTATION' if pidr_adv else 'BENCHMARK_MEASUREMENT_PRIMARY'
 report=f"""# Experiment 75 — Published Baseline Suite\n\n**RETROSPECTIVE_PUBLISHED_BASELINE_COMPARISON. Seed 4 is a previously opened evaluation set.**\n\nCORAL and MMD use the shared observable-prefix encoder and benign pre-exposure alignment only; PIDR-v1 is frozen and uniquely uses post-exposure paired separation. DeepLog is reported separately. The benchmark confirmatory claims are unchanged.\n\nRepresentation results are in the CSV tables. Paper positioning: **{position}**. Missing legacy sequence artifact values are explicitly marked rather than invented.\n""";(OUT/'EXPERIMENT_75_REPORT.md').write_text(report)
 raw_after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RES/'raw').glob('*.json')};assert raw_before==raw_after and hashlib.sha256(model_path.read_bytes()).hexdigest()==pidr_hash
 print(json.dumps({'position':position,'development':devrows,'evaluation':evrows,'deeplog':seqev,'new_rollouts':0},indent=2))
if __name__=='__main__':main()
