#!/usr/bin/env python3
"""Experiment 33: calibrated boundary gate before joint decoding."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from delegation_boundary_attribution_evaluation import sequence,split_standard
from models.boundary_gate import BoundaryGate
from models.joint_temporal_attribution_decoder import JointTemporalAttributionDecoder
from risk_emergence_learning import auroc,binary_f1
METHODS=('G0_joint_decoder_alone','G1_gate_alone','G2_gate_plus_joint')
def evaluate(split_name,sequences,onsets,reasons,gate,joint):
 gate_predictions=[gate.predict(x) for x in sequences];joint_predictions=[joint.predict(x) for x in sequences];rows=[]
 for method in METHODS:
  truth=[];scores=[];decisions=[];safe_false=[];joint_correct=[]
  for onset,reason,gp,jp in zip(onsets,reasons,gate_predictions,joint_predictions):
   decoded=joint.decode(jp);joint_score=1-jp.no_boundary_probability
   if method=='G0_joint_decoder_alone':score=joint_score;present=decoded is not None;final=decoded
   elif method=='G1_gate_alone':score=gp.boundary_probability;present=gp.boundary_present;final=None
   else:score=gp.boundary_probability*joint_score;present=gp.boundary_present and decoded is not None;final=decoded if present else None
   target=onset is not None;truth.append(int(target));scores.append(score);decisions.append(int(present))
   if not target:safe_false.append(present)
   elif method!='G1_gate_alone':joint_correct.append(final is not None and abs(final[0]-onset)<=1 and final[1]==reason)
  rows.append({'split':split_name,'method':method,'safe_false_boundary_rate':round(mean(safe_false),4),'boundary_presence_auroc':round(auroc(truth,scores),4),'boundary_presence_f1':round(binary_f1(truth,decisions),4),'conditional_joint_within_1_accuracy':round(mean(joint_correct),4) if joint_correct else '','gate_threshold':round(gate.decision_threshold,4) if method!='G0_joint_decoder_alone' else '','test_trajectories':len(sequences),'risky_trajectories':sum(truth)})
 return rows
def write_csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def write_svg(path,rows):
 rows=[x for x in rows if x['split']=='cross_domain_gui'];width,height=860,490;left,top,plot_h,plot_w=80,55,340,710;colors=['#2563eb','#f59e0b','#dc2626'];fields=(('safe_false_boundary_rate','Safe false boundary'),('boundary_presence_f1','Boundary F1'),('conditional_joint_within_1_accuracy','Conditional joint ±1'));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">','<rect width="100%" height="100%" fill="white"/>','<text x="430" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation Boundary Gate: GUI holdout</text>']
 for tick in range(6):v=tick/5;y=top+plot_h*(1-v);parts += [f'<line x1="{left}" y1="{y}" x2="{left+plot_w}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.1f}</text>']
 for fi,(field,label) in enumerate(fields):
  center=left+plot_w/3*(fi+.5);parts.append(f'<text x="{center}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="10">{label}</text>')
  for mi,row in enumerate(rows):value=float(row[field]) if row[field]!='' else 0;x=center+(mi-1)*52-18;y=top+plot_h*(1-value);parts.append(f'<rect x="{x}" y="{y}" width="36" height="{top+plot_h-y}" fill="{colors[mi]}"/>')
 for i,row in enumerate(rows):x=75+i*250;parts += [f'<rect x="{x}" y="{height-36}" width="12" height="12" fill="{colors[i]}"/>',f'<text x="{x+17}" y="{height-26}" font-family="sans-serif" font-size="9">{row["method"]}</text>']
 parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')
def main():
 p=argparse.ArgumentParser();base=ROOT/'benchmarks/boundary_attribution';p.add_argument('--tasks',type=Path,default=base/'tasks.json');p.add_argument('--trajectories',type=Path,default=base/'trajectories.json');p.add_argument('--labels',type=Path,default=base/'attribution_labels.json');p.add_argument('--output',type=Path,default=ROOT/'results/boundary_gate_evaluation.csv');p.add_argument('--plot',type=Path,default=ROOT/'results/boundary_gate_evaluation.svg');a=p.parse_args();tasks={x['task_id']:x for x in json.loads(a.tasks.read_text())};trajectories=json.loads(a.trajectories.read_text());labels={x['trajectory_id']:x for x in json.loads(a.labels.read_text())};observable=[(x,sequence(tasks[x['task_id']]['task'],x)) for x in trajectories];rows=[]
 for name,predicate in (('standard',lambda x:split_standard(x['task_id'])),('cross_domain_gui',lambda x:tasks[x['task_id']]['domain'] in {'coding','web'})):
  train=[pair for pair in observable if predicate(pair[0])];test=[pair for pair in observable if not predicate(pair[0])];train_seq=[x[1] for x in train];train_onsets=[labels[x[0]['trajectory_id']]['boundary_step'] for x in train];train_reasons=[labels[x[0]['trajectory_id']]['attribution'] for x in train];presence=[int(x is not None) for x in train_onsets];gate=BoundaryGate();gate.fit(train_seq,presence);joint=JointTemporalAttributionDecoder();joint.fit(train_seq,train_onsets,train_reasons);test_seq=[x[1] for x in test];test_onsets=[labels[x[0]['trajectory_id']]['boundary_step'] for x in test];test_reasons=[labels[x[0]['trajectory_id']]['attribution'] for x in test];rows.extend(evaluate(name,test_seq,test_onsets,test_reasons,gate,joint))
 write_csv(a.output,rows);write_svg(a.plot,rows);print(json.dumps({'results':rows,'gate_role':'trajectory-level boundary presence; temporal/reason decoding remains in the joint decoder','calibration':'threshold selected on an internal training-domain calibration split with safe false-boundary constraint','leakage_audit':'gate prediction accepts observable sequence only; supervision labels are fit targets, not inference features'},indent=2))
if __name__=='__main__':main()
