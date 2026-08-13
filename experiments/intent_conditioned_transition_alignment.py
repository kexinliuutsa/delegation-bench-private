#!/usr/bin/env python3
"""Experiment 39: expected transition conditioned on task intent."""
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
for entry in (ROOT,ROOT/'experiments'):
 if str(entry) not in sys.path:sys.path.insert(0,str(entry))
from models.intent_conditioned_transition_alignment import IntentConditionedTransitionAlignment
from models.joint_temporal_attribution_decoder import JointTemporalAttributionDecoder
from models.risk_emergence_model import ObservableEvent,ObservableSequence
from risk_emergence_learning import CDEMRiskModel,FrequencyModel,auroc,binary_f1

def observable(task,traj):return ObservableSequence(task,tuple(ObservableEvent(x['action'],x['observation'],x['capability'],x['delegation_state']) for x in traj['steps']))
def train_pair(pair):return int(pair.rsplit('_',1)[1])%10<7
def reason(pair):return 'external_effect_unrequested' if (int(pair.rsplit('_',1)[1])-1)%4 in (0,1) else 'irreversible_effect_unrequested'

class UnconditionalDTE:
 def fit(self,safe):
  from models.delegation_transition_encoder import transition_signature
  self.allowed={transition_signature(seq.events[i-1] if i else None,e) for seq in safe for i,e in enumerate(seq.events)}
 def predict(self,seq):
  from models.delegation_transition_encoder import transition_signature
  scores=[float(transition_signature(seq.events[i-1] if i else None,e) not in self.allowed) for i,e in enumerate(seq.events)];return scores,max(scores,default=0.)

def main():
 p=argparse.ArgumentParser();base=ROOT/'benchmarks/matched_action_boundary';p.add_argument('--tasks',type=Path,default=base/'tasks.json');p.add_argument('--trajectories',type=Path,default=base/'trajectories.json');p.add_argument('--labels',type=Path,default=base/'boundary_labels.json');p.add_argument('--output',type=Path,default=ROOT/'results/intent_conditioned_transition_alignment.csv');p.add_argument('--plot',type=Path,default=ROOT/'results/intent_conditioned_transition_alignment.svg');a=p.parse_args();tasks={x['task_id']:x for x in json.loads(a.tasks.read_text())};labels={x['trajectory_id']:x for x in json.loads(a.labels.read_text())};items=[]
 for tr in json.loads(a.trajectories.read_text()):items.append({'pair':tr['pair_id'],'id':tr['trajectory_id'],'sequence':observable(tasks[tr['task_id']]['task'],tr),'onset':labels[tr['trajectory_id']]['boundary_step']})
 train=[x for x in items if train_pair(x['pair'])];test=[x for x in items if not train_pair(x['pair'])];seq=[x['sequence'] for x in train];risk=[[int(x['onset'] is not None and i>=x['onset']) for i in range(1,4)] for x in train];onset=[[int(i==x['onset']) for i in range(1,4)] for x in train];safe=[x['sequence'] for x in train if x['onset'] is None];action=FrequencyModel('action');action.fit(seq,risk);cap=FrequencyModel('capability');cap.fit(seq,risk);cdem=CDEMRiskModel();cdem.fit(seq,risk,onset);dte=UnconditionalDTE();dte.fit(safe);aligned=IntentConditionedTransitionAlignment();aligned.fit(safe);joint=JointTemporalAttributionDecoder();joint.fit(seq,[x['onset'] for x in train],[reason(x['pair']) if x['onset'] else None for x in train]);models={'B0_action':action,'B1_capability':cap,'B2_cdem':cdem,'B3_dte_unconditional':dte,'B4_intent_conditioned_dte':aligned};rows=[]
 for name,model in models.items():
  truth=[];scores=[];decisions=[];safe_false=[];joint_ok=[]
  for x in test:
   if name=='B3_dte_unconditional':step_scores,score=model.predict(x['sequence']);present=score>=.5
   elif name=='B4_intent_conditioned_dte':pred=model.predict(x['sequence']);step_scores=list(pred.deviation_scores);score=pred.boundary_probability;present=pred.boundary_present
   else:pred=model.predict(x['sequence']);step_scores=list(pred.risk_probabilities);score=max(step_scores);present=score>=.5
   target=x['onset'] is not None;truth.append(int(target));scores.append(score);decisions.append(int(present))
   if not target:safe_false.append(present)
   else:
    decoded=joint.decode(joint.predict(x['sequence'])) if present else None;joint_ok.append(decoded is not None and abs(decoded[0]-x['onset'])<=1 and decoded[1]==reason(x['pair']))
  rows.append({'method':name,'boundary_auroc':round(auroc(truth,scores),4),'boundary_f1':round(binary_f1(truth,decisions),4),'safe_false_boundary_rate':round(mean(safe_false),4),'joint_decoder_within_1_accuracy':round(mean(joint_ok),4),'training_labels':('safe_only' if name=='B4_intent_conditioned_dte' else 'baseline-specific'),'test_pairs':30})
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 fields=(('boundary_auroc','AUROC'),('boundary_f1','Boundary F1'),('safe_false_boundary_rate','Safe false'),('joint_decoder_within_1_accuracy','Joint ±1'));w,h,left,top,pw,ph=980,500,75,55,840,340;colors=['#64748b','#f59e0b','#2563eb','#8b5cf6','#dc2626'];parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">','<rect width="100%" height="100%" fill="white"/>','<text x="490" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Intent-Conditioned Transition Alignment</text>']
 for tick in range(6):v=tick/5;y=top+ph*(1-v);parts += [f'<line x1="{left}" y1="{y}" x2="{left+pw}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.1f}</text>']
 for fi,(field,title) in enumerate(fields):
  center=left+pw/4*(fi+.5);parts.append(f'<text x="{center}" y="{top+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="10">{title}</text>')
  for i,row in enumerate(rows):value=float(row[field]);x=center+(i-2)*32-12;y=top+ph*(1-value);parts.append(f'<rect x="{x}" y="{y}" width="24" height="{top+ph-y}" fill="{colors[i]}"/>')
 for i,row in enumerate(rows):x=30+(i%3)*310;y=h-38+(i//3)*16;parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{colors[i]}"/>',f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="9">{row["method"]}</text>']
 parts.append('</svg>');a.plot.write_text('\n'.join(parts),encoding='utf-8');print(json.dumps({'results':rows,'B4_fit':'safe training trajectories only','matched_invariant':'action/capability/state transitions identical within each authorization pair','label_leakage':'B4 inference and fit receive no boundary, risk, or attribution labels'},indent=2))
if __name__=='__main__':main()
