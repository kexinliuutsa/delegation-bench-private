#!/usr/bin/env python3
"""Experiment 65: matched-vs-shuffled PIDR alignment and collapse audit."""
from __future__ import annotations
import argparse,csv,json,random
from pathlib import Path
from statistics import mean
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.cross_domain_monitor_transfer import load
from experiments.paradigm_invariant_delegation_representation import decorate,intervention_pairs,ordered,progress_pairs,representation_metrics,retrieval_eval
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation,euclidean,vectorize

def shuffled_progress_pairs(coding,web,seed):
 left,right=ordered(coding,seed),ordered(web,seed)
 if len(left)!=16 or len(right)!=16:raise ValueError('fixed protocol requires 4 tasks x 4 styles per seed')
 # Sorted order is task-major/style-minor. Rotate task family while retaining
 # seed, style, cardinality, and normalized progress alignment.
 shuffled=[right[((task+1)%4)*4+style] for task in range(4) for style in range(4)]
 return progress_pairs(left,shuffled)

def collapse_metrics(encoder,coding,web):
 controls=ordered(coding,2)+ordered(web,2);embeddings=[]
 for trajectory in controls:
  for index,event in enumerate(trajectory['steps']):
   raw=vectorize(trajectory,event,index);embeddings.append(encoder.encode_vector(raw) if encoder else raw)
 rng=random.Random(6501);between=[]
 for _ in range(min(5000,len(embeddings)*(len(embeddings)-1)//2)):
  a,b=rng.sample(embeddings,2);between.append(euclidean(a,b))
 intervention=[]
 for domain in (coding,web):
  for a,b in intervention_pairs(domain,{2}):intervention.append(encoder.distance(a,b) if encoder else euclidean(a,b))
 centroid=[sum(row[i] for row in embeddings)/len(embeddings) for i in range(len(embeddings[0]))]
 variance=mean(euclidean(row,centroid)**2 for row in embeddings)
 return {'heldout_control_pairwise_distance':round(mean(between),6),'heldout_latent_variance':round(variance,8),'control_treatment_distance':round(mean(intervention),6),'collapse_ratio':round(mean(intervention)/(mean(between) or 1),4),'collapsed':variance<1e-8}

def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--full-model',type=Path,default=base/'pidr/pidr_model.json');p.add_argument('--pidr-summary',type=Path,default=base/'pidr/summary.json');p.add_argument('--output-dir',type=Path,default=base/'pidr_shuffled_alignment');a=p.parse_args();cohorts=load(a.rollouts);decorate(cohorts);coding=cohorts['gpt5_minimal_coding_agent'];web=cohorts['gpt5_minimal_web_agent'];shuffled=[]
 for seed in (0,1):shuffled+=shuffled_progress_pairs(coding,web,seed)
 negatives=intervention_pairs(coding,{0,1})+intervention_pairs(web,{0,1});model=ParadigmInvariantDelegationRepresentation();model.fit(shuffled,negatives);benign,separation,ratio=representation_metrics(model,coding,web);shuffled_row={'method':'B1_PIDR_shuffled_alignment','cross_benign_distance':round(benign,6),'intervention_separation':round(separation,6),'separation_alignment_ratio':round(ratio,4),**retrieval_eval(model,coding,web)};prior=json.loads(a.pidr_summary.read_text())['results'];raw=next(dict(x) for x in prior if x['method']=='B1_raw_action_encoder');raw['method']='B0_raw_encoder';full=next(dict(x) for x in prior if x['method']=='B2_PIDR');full['method']='B2_PIDR_correct_alignment';rows=[raw,shuffled_row,full];full_model=ParadigmInvariantDelegationRepresentation.load(a.full_model);collapse=[{'method':'B0_raw_encoder',**collapse_metrics(None,coding,web)},{'method':'B1_PIDR_shuffled_alignment',**collapse_metrics(model,coding,web)},{'method':'B2_PIDR_correct_alignment',**collapse_metrics(full_model,coding,web)}];a.output_dir.mkdir(parents=True,exist_ok=True);model.save(a.output_dir/'pidr_shuffled_model.json')
 with (a.output_dir/'shuffled_alignment_results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 with (a.output_dir/'latent_collapse_audit.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(collapse[0]));w.writeheader();w.writerows(collapse)
 report={'experiment':65,'changed_variable':'correct versus task-family-rotated benign alignment','shuffle_controls':['same seed','same injection style','same pair count','same normalized progress alignment'],'training_seeds':[0,1],'heldout_seed':2,'shuffled_positive_pair_count':len(shuffled),'negative_pair_count':len(negatives),'results':rows,'latent_collapse_audit':collapse};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
