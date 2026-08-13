#!/usr/bin/env python3
"""Experiment 35: identical observable actions under different task authority."""
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
for entry in (ROOT,ROOT/'experiments'):
 if str(entry) not in sys.path:sys.path.insert(0,str(entry))
from models.risk_emergence_model import ObservableEvent,ObservableSequence,RiskEmergenceModel
from risk_emergence_learning import FrequencyModel,auroc,binary_f1

def observable(task,trajectory):
 return ObservableSequence(task,tuple(ObservableEvent(x['action'],x['observation'],x['capability'],x['delegation_state']) for x in trajectory['steps']))

def split_pair(pair_id):return int(pair_id.rsplit('_',1)[1])%10<7

def write_csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def write_svg(path,rows):
 fields=(('trajectory_boundary_accuracy','Boundary accuracy'),('matched_pair_joint_accuracy','Matched-pair accuracy'),('safe_false_boundary_rate','Safe false boundary'));colors=['#64748b','#f59e0b','#8b5cf6','#dc2626'];w,h,left,top,pw,ph=980,500,75,55,830,340;parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">','<rect width="100%" height="100%" fill="white"/>','<text x="490" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Matched Action Boundary Test</text>']
 for tick in range(6):
  v=tick/5;y=top+ph*(1-v);parts += [f'<line x1="{left}" y1="{y}" x2="{left+pw}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.1f}</text>']
 for fi,(field,title) in enumerate(fields):
  center=left+pw/3*(fi+.5);parts.append(f'<text x="{center}" y="{top+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="11">{title}</text>')
  for i,row in enumerate(rows):
   value=float(row[field]);x=center+(i-1.5)*42-15;y=top+ph*(1-value);parts.append(f'<rect x="{x}" y="{y}" width="30" height="{top+ph-y}" fill="{colors[i]}"/>')
 for i,row in enumerate(rows):
  x=50+(i%2)*455;y=h-42+(i//2)*17;parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{colors[i]}"/>',f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{row["method"]}</text>']
 parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')

def main():
 p=argparse.ArgumentParser();base=ROOT/'benchmarks/matched_action_boundary';p.add_argument('--tasks',type=Path,default=base/'tasks.json');p.add_argument('--trajectories',type=Path,default=base/'trajectories.json');p.add_argument('--labels',type=Path,default=base/'boundary_labels.json');p.add_argument('--output',type=Path,default=ROOT/'results/matched_action_boundary.csv');p.add_argument('--plot',type=Path,default=ROOT/'results/matched_action_boundary.svg');a=p.parse_args()
 tasks={x['task_id']:x for x in json.loads(a.tasks.read_text())};trajectories=json.loads(a.trajectories.read_text());labels={x['trajectory_id']:x for x in json.loads(a.labels.read_text())}
 train=[];test=[]
 for trajectory in trajectories:
  item=(trajectory['pair_id'],trajectory['trajectory_id'],observable(tasks[trajectory['task_id']]['task'],trajectory))
  (train if split_pair(trajectory['pair_id']) else test).append(item)
 train_sequences=[x[2] for x in train];risk=[];onset=[]
 for _,trajectory_id,sequence in train:
  boundary=labels[trajectory_id]['boundary_step'];risk.append([int(i==boundary) for i in range(1,len(sequence.events)+1)]);onset.append(risk[-1][:])
 models={'A0_action_only':FrequencyModel('action'),'A1_capability_only':FrequencyModel('capability'),'A2_delegation_state_only':FrequencyModel('state'),'A3_intent_conditioned_sequence':RiskEmergenceModel()}
 for name,model in models.items():model.fit(train_sequences,risk,onset) if name.startswith('A3') else model.fit(train_sequences,risk)
 rows=[]
 for name,model in models.items():
  truth=[];scores=[];predictions={};errors=[]
  for pair_id,trajectory_id,sequence in test:
   prediction=model.predict(sequence);score=max(prediction.risk_probabilities);target=labels[trajectory_id]['boundary_step'];truth.append(int(target is not None));scores.append(score);predictions[trajectory_id]=int(score>=.5)
   if target is not None:
    guessed=max(range(len(prediction.onset_distribution)),key=lambda i:prediction.onset_distribution[i])+1;errors.append(abs(guessed-target))
  binary=[int(x>=.5) for x in scores];groups=defaultdict(list)
  for pair_id,trajectory_id,_ in test:groups[pair_id].append((trajectory_id,labels[trajectory_id]['boundary_step']))
  pair_joint=[];sensitivity=[]
  for values in groups.values():
   safe=next(tid for tid,b in values if b is None);risky=next(tid for tid,b in values if b is not None);pair_joint.append(predictions[safe]==0 and predictions[risky]==1);sensitivity.append(predictions[safe]!=predictions[risky])
  safe_predictions=[pred for pred,target in zip(binary,truth) if not target]
  rows.append({'method':name,'trajectory_boundary_accuracy':round(mean(a==b for a,b in zip(truth,binary)),4),'boundary_auroc':round(auroc(truth,scores),4),'boundary_f1':round(binary_f1(truth,binary),4),'safe_false_boundary_rate':round(mean(safe_predictions),4),'matched_pair_joint_accuracy':round(mean(pair_joint),4),'pair_context_sensitivity':round(mean(sensitivity),4),'onset_mae':round(mean(errors),3),'test_pairs':len(groups)})
 write_csv(a.output,rows);write_svg(a.plot,rows);print(json.dumps({'train_pairs':70,'test_pairs':30,'matched_invariant':'action, observation, capability, and delegation-state sequences are identical within every pair','labels_separate_from_inference':True,'results':rows},indent=2))
if __name__=='__main__':main()
