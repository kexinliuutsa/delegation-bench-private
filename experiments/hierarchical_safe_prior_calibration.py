#!/usr/bin/env python3
"""Experiment 40: task-conditioned safe-prior calibration."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
for entry in (ROOT,ROOT/'experiments'):
 if str(entry) not in sys.path:sys.path.insert(0,str(entry))
from models.hierarchical_safe_delegation_prior import HierarchicalSafeDelegationPrior
from models.intent_conditioned_transition_alignment import IntentConditionedTransitionAlignment
from models.risk_emergence_model import ObservableEvent,ObservableSequence
from risk_emergence_learning import CDEMRiskModel,FrequencyModel,auroc,binary_f1

def observable(task,tr):return ObservableSequence(task,tuple(ObservableEvent(x['action'],x['observation'],x['capability'],x['delegation_state']) for x in tr['steps']))
def train_pair(pair):return int(pair.rsplit('_',1)[1])%10<7
def ece(labels,scores,bins=10):
 total=len(labels);value=0.
 for index in range(bins):
  selected=[i for i,x in enumerate(scores) if index/bins<=x<((index+1)/bins if index<bins-1 else 1.000001)]
  if selected:value+=len(selected)/total*abs(mean(scores[i] for i in selected)-mean(labels[i] for i in selected))
 return value
def brier(labels,scores):return mean((a-b)**2 for a,b in zip(labels,scores))

def main():
 p=argparse.ArgumentParser();base=ROOT/'benchmarks/matched_action_boundary';p.add_argument('--tasks',type=Path,default=base/'tasks.json');p.add_argument('--trajectories',type=Path,default=base/'trajectories.json');p.add_argument('--labels',type=Path,default=base/'boundary_labels.json');p.add_argument('--output',type=Path,default=ROOT/'results/hierarchical_safe_prior_calibration.csv');p.add_argument('--plot',type=Path,default=ROOT/'results/hierarchical_safe_prior_calibration.svg');a=p.parse_args();tasks={x['task_id']:x for x in json.loads(a.tasks.read_text())};labels={x['trajectory_id']:x for x in json.loads(a.labels.read_text())};items=[]
 for tr in json.loads(a.trajectories.read_text()):items.append((tr['pair_id'],tr['trajectory_id'],observable(tasks[tr['task_id']]['task'],tr),labels[tr['trajectory_id']]['boundary_step']))
 train=[x for x in items if train_pair(x[0])];test=[x for x in items if not train_pair(x[0])];seq=[x[2] for x in train];risk=[[int(x[3] is not None and i>=x[3]) for i in range(1,4)] for x in train];onset=[[int(i==x[3]) for i in range(1,4)] for x in train];safe=[x[2] for x in train if x[3] is None];models={'B0_action':FrequencyModel('action'),'B2_cdem_supervised_upper_bound':CDEMRiskModel(),'B4_intent_dte':IntentConditionedTransitionAlignment(),'B5_hierarchical_safe_prior':HierarchicalSafeDelegationPrior()};models['B0_action'].fit(seq,risk);models['B2_cdem_supervised_upper_bound'].fit(seq,risk,onset);models['B4_intent_dte'].fit(safe);models['B5_hierarchical_safe_prior'].fit(safe);rows=[]
 for name,model in models.items():
  truth=[];scores=[];decisions=[];safe_false=[]
  for _,_,sequence,boundary in test:
   target=int(boundary is not None)
   if name=='B4_intent_dte':prediction=model.predict(sequence);score=prediction.boundary_probability;decision=prediction.boundary_present
   elif name=='B5_hierarchical_safe_prior':prediction=model.predict(sequence);score=prediction.boundary_probability;decision=prediction.boundary_present
   else:prediction=model.predict(sequence);score=max(prediction.risk_probabilities);decision=score>=.5
   truth.append(target);scores.append(score);decisions.append(int(decision))
   if not target:safe_false.append(decision)
  rows.append({'method':name,'boundary_auroc':round(auroc(truth,scores),4),'boundary_f1':round(binary_f1(truth,decisions),4),'safe_false_boundary_rate':round(mean(safe_false),4),'ece_10_bin':round(ece(truth,scores),4),'brier_score':round(brier(truth,scores),4),'training_regime':'safe_only' if name in ('B4_intent_dte','B5_hierarchical_safe_prior') else 'boundary_supervised','safe_rare_types':'external communication; transaction; deletion; persistent permission change','test_pairs':30})
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 fields=(('boundary_auroc','AUROC'),('boundary_f1','F1'),('safe_false_boundary_rate','Safe false'),('brier_score','Brier'));w,h,left,top,pw,ph=960,500,75,55,820,340;colors=['#64748b','#2563eb','#8b5cf6','#dc2626'];parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">','<rect width="100%" height="100%" fill="white"/>','<text x="480" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Hierarchical Safe Prior Calibration</text>']
 for tick in range(6):v=tick/5;y=top+ph*(1-v);parts += [f'<line x1="{left}" y1="{y}" x2="{left+pw}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.1f}</text>']
 for fi,(field,title) in enumerate(fields):
  center=left+pw/4*(fi+.5);parts.append(f'<text x="{center}" y="{top+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="10">{title}</text>')
  for i,row in enumerate(rows):value=float(row[field]);x=center+(i-1.5)*38-14;y=top+ph*(1-value);parts.append(f'<rect x="{x}" y="{y}" width="28" height="{top+ph-y}" fill="{colors[i]}"/>')
 for i,row in enumerate(rows):x=35+(i%2)*455;y=h-40+(i//2)*17;parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{colors[i]}"/>',f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="9">{row["method"]}</text>']
 parts.append('</svg>');a.plot.write_text('\n'.join(parts),encoding='utf-8');print(json.dumps({'results':rows,'B5_training':'safe trajectories only; task regimes induced from embeddings','safe_rare_cases':['authorized send','authorized purchase','authorized delete','authorized permission change'],'matched_control':'each rare-valid case has an identical-transition unsupported counterpart'},indent=2))
if __name__=='__main__':main()
