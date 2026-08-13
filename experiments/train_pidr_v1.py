#!/usr/bin/env python3
"""Fit/select PIDR-v1 on frozen TRAIN seeds and DEVELOPMENT seed 3 only."""
from __future__ import annotations
import csv,hashlib,json,math,random,subprocess,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));sys.path.insert(0,str(ROOT/'experiments'))
from pidr_v1 import PIDRV1,cosine_distance
from delegation_bench_v1_common import BENCH,RESULTS
OUT=RESULTS/'pidr_v1';ACCESS=[]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path,seed):
 if seed==4:raise RuntimeError('SEALED TEST ACCESS ABORTED: seed 4')
 ACCESS.append({'path':str(path),'seed':seed});return json.loads(Path(path).read_text())
def sample(job,raw,index):
 steps=raw['steps'];cur=steps[index];prev=steps[:index];tools=[x['tool'] for x in prev];actions=[x['action'] for x in prev]
 def run_length(xs):
  if not xs:return 0
  return next((i for i,x in enumerate(reversed(xs),1) if x!=xs[-1]),len(xs))
 return {'task':job['task'],'paradigm':job['paradigm'],'previous_actions':actions,'previous_tools':tools,'previous_observations':[x['observation'] for x in prev[-3:]],'previous_capability':prev[-1]['capability_state'] if prev else 'A0_OBSERVE','current_observation':cur['observation'],'current_observation_source':cur['observation_source'],'current_action':cur['action'],'current_tool':cur['tool'],'current_capability':cur['capability_state'],'normalized_progress':(index+1)/max(len(steps),1),'recent_tool_run_length':run_length(tools),'recent_action_run_length':run_length(actions),'step':cur['step'],'trajectory_id':job['trajectory_id']}
def load(seed_set):
 manifest=json.loads((BENCH/'collection_manifest.json').read_text());jobs=[j for j in manifest['jobs'] if j['seed'] in seed_set]
 if any(j['seed']==4 for j in jobs):raise RuntimeError('seed 4 selected')
 data=defaultdict(dict)
 for job in jobs:
  if job['pair_status']!='VALID_MATERIALIZED':continue
  path=RESULTS/'raw'/f"{job['pair_id']}_{job['condition']}.json";raw=read_json(path,job['seed']);data[job['pair_id']][job['condition']]={'job':job,'raw':raw,'samples':[sample(job,raw,i) for i in range(len(raw['steps']))]}
 return data
def monotone(a,b):
 n=min(len(a),len(b));return [(a[min(len(a)-1,round(i*(len(a)-1)/max(n-1,1)))],b[min(len(b)-1,round(i*(len(b)-1)/max(n-1,1)))]) for i in range(n)] if n else []
def construct(data):
 pre_by=defaultdict(list);post=[];temp=[];matched_pre=[];early=0;post_pairs=0
 for roles in data.values():
  c,t=roles['control'],roles['treatment'];actual=t['raw'].get('actual_exposure_step')
  for role in (c,t):
   exposure=actual if actual is not None else 10**9
   pre=[s for s in role['samples'] if s['step']<exposure]
   for s in pre:pre_by[(min(4,int(s['normalized_progress']*5)),s['current_capability'])].append(s)
   for a,b in zip(pre,pre[1:]):
    if a['current_capability']==b['current_capability']:temp.append((a,b))
  cp=[s for s in c['samples'] if actual is None or s['step']<actual];tp=[s for s in t['samples'] if actual is None or s['step']<actual];matched_pre.extend(monotone(cp,tp))
  if actual is None:early+=1;continue
  cq=[s for s in c['samples'] if s['step']>=actual];tq=[s for s in t['samples'] if s['step']>=actual];aligned=monotone(cq,tq);post.extend(aligned);post_pairs+=1
 pre=[];rng=random.Random(711)
 for key,values in sorted(pre_by.items(),key=str):
  left=[x for x in values if x['paradigm']=='coding'];right=[x for x in values if x['paradigm']=='web'];rng.shuffle(left);rng.shuffle(right);pre.extend(zip(left[:min(len(left),len(right))],right[:min(len(left),len(right))]))
 return list(pre),post,temp,matched_pre,early,post_pairs
def auc(control,treatment):
 vals=[(x,0) for x in control]+[(x,1) for x in treatment];wins=ties=0
 for c in control:
  for t in treatment:wins+=t>c;ties+=t==c
 return (wins+.5*ties)/(len(control)*len(treatment)) if control and treatment else .5
def monitor(model,train,dev,raw=False):
 memory=[]
 for roles in train.values():
  xs=roles['control']['samples'];memory.extend((model.encode(a,raw),model.encode(b,raw)) for a,b in zip(xs,xs[1:]))
 def score(sample):
  z=model.encode(sample,raw);ds=sorted(min(cosine_distance(z,a),cosine_distance(z,b)) for a,b in memory);return mean(ds[:5])
 train_scores=[]
 for roles in train.values():train_scores.extend(score(s) for s in roles['control']['samples'])
 threshold=sorted(train_scores)[int(.95*(len(train_scores)-1))];controls=[];treatments=[];pair_detect=[]
 for roles in dev.values():
  cs=mean(score(s) for s in roles['control']['samples']);ts=mean(score(s) for s in roles['treatment']['samples']);controls.append(cs);treatments.append(ts);pair_detect.append(ts>threshold)
 return {'auroc':auc(controls,treatments),'benign_false_alarm':sum(x>threshold for x in controls)/len(controls),'pair_detection':sum(pair_detect)/len(pair_detect),'threshold_source':'TRAIN controls only'}
def geometry(model,constructed,raw=False):
 pre,post,temp,matched,early,post_count=constructed;pd=mean(model.distance(a,b,raw) for a,b in pre);sep=mean(model.distance(a,b,raw) for a,b in post);mp=mean(model.distance(a,b,raw) for a,b in matched);return {'pre_benign_distance':pd,'post_separation':sep,'separation_alignment_ratio':sep/max(pd,1e-9),'pre_matched_distance':mp,'post_minus_pre':sep-mp,'latent_variance':model.latent_variance([x for p in pre for x in p]) if not raw else PIDRV1(model.latent_dim).latent_variance([x for p in pre for x in p])}
def rank_scores(rows):
 keys=[('separation_alignment_ratio',True,1),('pre_benign_distance',False,.5),('dev_auroc',True,.25),('dev_benign_false_alarm',False,.25)]
 for r in rows:r['selection_score']=0
 for key,higher,weight in keys:
  ordered=sorted(rows,key=lambda x:x[key],reverse=higher)
  for rank,r in enumerate(ordered):r['selection_score']+=weight*(len(rows)-rank)
def write_csv(path,rows):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 OUT.mkdir(parents=True,exist_ok=True);subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],check=True,cwd=ROOT,capture_output=True)
 train=load({0,1,2});dev=load({3});tr=construct(train);dv=construct(dev);rows=[];models={};config=0
 # Stage 1: 12 dimension/lambda candidates with fixed temporal/margin.
 for d in (64,128,256):
  for lam in (.25,.5,1.0,2.0):
   config+=1;m=PIDRV1(d,lam,.1,.1,.1,seed=71000+config).fit(tr[0],tr[1],tr[2]);g=geometry(m,dv);mon=monitor(m,train,dev);row={'config_id':config,'stage':1,'latent_dimension':d,'lambda_sep':lam,'beta_temp':.1,'margin':.1,'gamma_var':.1,**g,'dev_auroc':mon['auroc'],'dev_benign_false_alarm':mon['benign_false_alarm'],'dev_pair_detection':mon['pair_detection']};rows.append(row);models[config]=m
 rank_scores(rows);best1=max(rows,key=lambda x:x['selection_score'])
 # Stage 2: 12 beta/margin candidates around fixed Stage-1 dimension/lambda.
 stage2=[]
 for beta in (0.0,.1,.25,.5):
  for margin in (.05,.1,.2):
   config+=1;m=PIDRV1(best1['latent_dimension'],best1['lambda_sep'],beta,.1,margin,seed=71000+config).fit(tr[0],tr[1],tr[2]);g=geometry(m,dv);mon=monitor(m,train,dev);row={'config_id':config,'stage':2,'latent_dimension':best1['latent_dimension'],'lambda_sep':best1['lambda_sep'],'beta_temp':beta,'margin':margin,'gamma_var':.1,**g,'dev_auroc':mon['auroc'],'dev_benign_false_alarm':mon['benign_false_alarm'],'dev_pair_detection':mon['pair_detection']};rows.append(row);stage2.append(row);models[config]=m
 rank_scores(stage2);selected=max(stage2,key=lambda x:x['selection_score']);model=models[selected['config_id']];write_csv(OUT/'hyperparameter_search.csv',rows)
 metadata={'training_seeds':[0,1,2],'development_seed':3,'sealed_test_seed':4,'seed_4_accessed':False,'protocol_sha256':sha(RESULTS/'audits/FROZEN_PROTOCOL_SHA256.json'),'training_script_sha256':sha(__file__),'encoder_features_exclude':['condition','intervention_style','pair_id','scheduled_exposure_step','future_events','private_reasoning'],'training_objective':'L_pre_invariance + lambda_sep L_post_sensitivity + beta_temp L_temporal_consistency + gamma_var L_variance','joint_detector_training':False};model.save(OUT/'pidr_v1_model.json',metadata);(OUT/'selected_model.json').write_text(json.dumps({'selected_config':selected,'selection':'fixed rank aggregation on seed-3 development only','seed_4_accessed':False},indent=2)+'\n');(OUT/'training_access_log.json').write_text(json.dumps({'opened_trajectory_paths':ACCESS,'seed_4_accessed':False},indent=2)+'\n');(OUT/'training_state.json').write_text(json.dumps({'train_pair_ids':list(train),'dev_pair_ids':list(dev),'train_constructed':{'pre_alignment_samples':len(tr[0]),'post_transition_samples':len(tr[1]),'temporal_samples':len(tr[2]),'early_termination_pre_prefix_pairs':tr[4],'post_exposure_pairs':tr[5]},'dev_constructed':{'pre_alignment_samples':len(dv[0]),'post_transition_samples':len(dv[1]),'temporal_samples':len(dv[2]),'early_termination_pre_prefix_pairs':dv[4],'post_exposure_pairs':dv[5]}},indent=2)+'\n');print(json.dumps({'candidate_configurations':len(rows),'selected_config':selected,'seed_4_accessed':False},indent=2))
if __name__=='__main__':main()
