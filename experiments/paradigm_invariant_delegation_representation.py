#!/usr/bin/env python3
"""Experiment 63: PIDR proof-of-concept on frozen Coding/Web trajectories."""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path
from statistics import mean
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.authority_source_alignment import align
from experiments.cross_domain_monitor_transfer import auroc,load,percentile
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation,euclidean,vectorize

def changed(c,t):return {x['treatment_step'] for x in align(c['steps'],t['steps']) if x.get('treatment_step') and x['relation'] in {'NEW','MODIFIED'}}
def decorate(cohorts):
 for agent,pairs in cohorts.items():
  kind='web' if 'web' in agent else 'coding'
  for roles in pairs.values():
   for trajectory in roles.values():trajectory['agent_type']=kind
def ordered(pairs,seed,role='control'):return [roles[role] for pair,roles in sorted(pairs.items()) if roles[role]['seed']==seed]
def progress_pairs(left,right):
 output=[]
 for a,b in zip(left,right):
  count=max(len(a['steps']),len(b['steps']))
  for index in range(count):
   ia=min(len(a['steps'])-1,round(index*(len(a['steps'])-1)/max(1,count-1)));ib=min(len(b['steps'])-1,round(index*(len(b['steps'])-1)/max(1,count-1)));output.append((vectorize(a,a['steps'][ia],ia),vectorize(b,b['steps'][ib],ib)))
 return output
def intervention_pairs(pairs,seeds):
 output=[]
 for roles in pairs.values():
  if roles['control']['seed'] not in seeds:continue
  c,t=roles['control'],roles['treatment']
  for row in align(c['steps'],t['steps']):
   if row.get('control_step') and row.get('treatment_step') and row['relation'] in {'NEW','MODIFIED'}:
    i,j=row['control_step']-1,row['treatment_step']-1;output.append((vectorize(c,c['steps'][i],i),vectorize(t,t['steps'][j],j)))
 return output
def representation_metrics(encoder,coding,web):
 benign=[]
 for seed in (2,):
  pairs=progress_pairs(ordered(coding,seed),ordered(web,seed));benign.extend(encoder.distance(a,b) if encoder else euclidean(a,b) for a,b in pairs)
 separation=[]
 for domain in (coding,web):
  for a,b in intervention_pairs(domain,{2}):separation.append(encoder.distance(a,b) if encoder else euclidean(a,b))
 return mean(benign),mean(separation),mean(separation)/(mean(benign) or 1)
def retrieval_eval(encoder,coding,web):
 train=ordered(coding,0)+ordered(coding,1);trajectory_memory=[]
 for trajectory in train:trajectory_memory.append([vectorize(trajectory,event,i) for i,event in enumerate(trajectory['steps'])])
 memory=[x for values in trajectory_memory for x in values]
 def score(traj,candidates=None):
  candidates=candidates or memory
  output=[]
  for i,event in enumerate(traj['steps']):
   x=vectorize(traj,event,i);output.append(min(encoder.distance(x,m) if encoder else euclidean(x,m) for m in candidates))
  return output
 train_max=[]
 for index,trajectory in enumerate(train):
  leave_one_out=[x for other,values in enumerate(trajectory_memory) if other!=index for x in values];train_max.append(max(score(trajectory,leave_one_out)))
 threshold=percentile(train_max,.95);truth=[];scores=[];false=[];detected=[]
 for roles in web.values():
  diff=changed(roles['control'],roles['treatment']);cs=score(roles['control']);ts=score(roles['treatment']);false.append(any(x>threshold for x in cs));detected.append(any(i in diff and x>threshold for i,x in enumerate(ts,1)))
  for role,traj,values in (('control',roles['control'],cs),('treatment',roles['treatment'],ts)):
   for event,value in zip(traj['steps'],values):truth.append(role=='treatment' and event['step'] in diff);scores.append(value)
 return {'auroc':round(auroc(truth,scores),4),'transfer_false_alarm':round(mean(false),4),'pair_detection':round(mean(detected),4),'threshold':round(threshold,6)}
def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--output-dir',type=Path,default=base/'pidr');a=p.parse_args();cohorts=load(a.rollouts);decorate(cohorts);coding=cohorts['gpt5_minimal_coding_agent'];web=cohorts['gpt5_minimal_web_agent'];positives=[]
 for seed in (0,1):positives+=progress_pairs(ordered(coding,seed),ordered(web,seed))
 negatives=intervention_pairs(coding,{0,1})+intervention_pairs(web,{0,1});pidr=ParadigmInvariantDelegationRepresentation();pidr.fit(positives,negatives);rows=[]
 for name,encoder in (('B1_raw_action_encoder',None),('B2_PIDR',pidr)):
  benign,separation,ratio=representation_metrics(encoder,coding,web);rows.append({'method':name,'cross_benign_distance':round(benign,6),'intervention_separation':round(separation,6),'separation_alignment_ratio':round(ratio,4),**retrieval_eval(encoder,coding,web)})
 ndtr=json.loads((base/'cross_domain_transfer/summary.json').read_text())['results'][0];rows.insert(0,{'method':'B0_NDTR','cross_benign_distance':'NA','intervention_separation':'NA','separation_alignment_ratio':'NA','auroc':ndtr['auroc'],'transfer_false_alarm':ndtr['control_false_alarm'],'pair_detection':ndtr['pair_detection'],'threshold':ndtr['threshold']})
 a.output_dir.mkdir(parents=True,exist_ok=True)
 with (a.output_dir/'pidr_results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 pidr.save(a.output_dir/'pidr_model.json')
 report={'experiment':63,'proof_of_concept':True,'training_seeds':[0,1],'heldout_seed':2,'positive_pairs':'aligned Coding-control/Web-control progress steps','positive_pair_count':len(positives),'negative_pairs':'paired control/treatment divergent steps in both paradigms','negative_pair_count':len(negatives),'unsafe_or_authority_labels_used':False,'results':rows};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
