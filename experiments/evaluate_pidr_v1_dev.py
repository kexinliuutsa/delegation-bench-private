#!/usr/bin/env python3
"""Development-only PIDR-v1 geometry, monitor, ablations, and probes."""
from __future__ import annotations
import csv,json,math,random,subprocess,sys
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));sys.path.insert(0,str(ROOT/'experiments'))
from pidr_v1 import PIDRV1
from train_pidr_v1 import OUT,load,construct,geometry,monitor,write_csv
from delegation_bench_v1_common import RESULTS
def probe(model,train,dev,raw=False):
 # Deterministic nearest-centroid linear probe fit on TRAIN vectors only.
 samples=[]
 for roles in train.values():samples.extend((model.encode(s,raw),s['paradigm']) for s in roles['control']['samples'])
 centroids={}
 for p in ('coding','web'):
  xs=[z for z,y in samples if y==p];centroids[p]=[mean(v) for v in zip(*xs)]
 correct=total=0
 for roles in dev.values():
  for s in roles['control']['samples']:
   z=model.encode(s,raw);pred=min(centroids,key=lambda p:sum((a-b)**2 for a,b in zip(z,centroids[p])));correct+=pred==s['paradigm'];total+=1
 return correct/total
def main():
 subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],check=True,cwd=ROOT,capture_output=True);artifact=json.loads((OUT/'pidr_v1_model.json').read_text());assert artifact['seed_4_accessed'] is False;selected=PIDRV1.from_dict(artifact);train=load({0,1,2});dev=load({3});tr,dv=construct(train),construct(dev)
 raw_geom=geometry(selected,dv,True);raw_mon=monitor(selected,train,dev,True);full_geom=geometry(selected,dv);full_mon=monitor(selected,train,dev)
 reps=[{'representation':'Raw',**raw_geom},{'representation':'PIDR-v1',**full_geom}];write_csv(OUT/'dev_representation_metrics.csv',reps);write_csv(OUT/'dev_monitor_metrics.csv',[{'representation':'Raw',**raw_mon},{'representation':'PIDR-v1',**full_mon}])
 variants=[]
 specs=[('A0_Raw',None),('A1_no_pre',{'pre':False}),('A2_no_post',{'post':False}),('A3_no_temporal',{'temp':False}),('A4_Full',{})]
 for i,(name,flags) in enumerate(specs):
  if flags is None:m=selected;g=geometry(m,dv,True);mon=monitor(m,train,dev,True);var=g['latent_variance']
  else:
   m=PIDRV1(selected.latent_dim,selected.lambda_sep,selected.beta_temp,selected.gamma_var,selected.margin,seed=71200+i).fit(tr[0] if flags.get('pre',True) else [],tr[1] if flags.get('post',True) else [],tr[2] if flags.get('temp',True) else []);g=geometry(m,dv);mon=monitor(m,train,dev);var=g['latent_variance']
  variants.append({'variant':name,'benign_cross_paradigm_distance':g['pre_benign_distance'],'post_exposure_separation':g['post_separation'],'ratio':g['separation_alignment_ratio'],'dev_auroc':mon['auroc'],'dev_benign_false_alarm':mon['benign_false_alarm'],'dev_pair_detection':mon['pair_detection'],'latent_variance':var,'collapse_detected':var<.005})
 write_csv(OUT/'ablation_results.csv',variants)
 temporal=[]
 for split_name,data,con in (('TRAIN',train,tr),('DEVELOPMENT',dev,dv)):
  pre=mean(selected.distance(a,b) for a,b in con[3]);post=mean(selected.distance(a,b) for a,b in con[1]);temporal.append({'split':split_name,'pre_matched_distance':pre,'post_matched_distance':post,'post_minus_pre':post-pre})
 write_csv(OUT/'temporal_negative_control.csv',temporal);probes=[{'representation':'Raw','development_paradigm_accuracy':probe(selected,train,dev,True),'classifier':'TRAIN nearest-centroid linear geometry probe'},{'representation':'PIDR-v1','development_paradigm_accuracy':probe(selected,train,dev),'classifier':'TRAIN nearest-centroid linear geometry probe'}];write_csv(OUT/'paradigm_probe.csv',probes)
 report={'train_pairs_used':len(train),'development_pairs_used':len(dev),'early_termination_pre_prefixes_used':tr[4],'post_exposure_pairs_used':tr[5],'selected_hyperparameters':{k:artifact[k] for k in ('latent_dimension','lambda_sep','beta_temp','margin','gamma_var')},'raw_representation':raw_geom,'pidr_representation':full_geom,'raw_monitor':raw_mon,'pidr_monitor':full_mon,'temporal_negative_control':temporal,'paradigm_probe':probes,'collapse_detected':variants[-1]['collapse_detected'],'seed_4_accessed':False,'pidr_is_representation_learner':True};(OUT/'training_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
