#!/usr/bin/env python3
"""Experiment 32: direct decoding of joint temporal-attribution boundaries."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from delegation_boundary_attribution_evaluation import macro_attr_f1,sequence,split_standard
from models.delegation_boundary_attribution_model import ATTRIBUTIONS,DelegationBoundaryAttributionModel
from models.joint_temporal_attribution_decoder import JointTemporalAttributionDecoder
METHODS=('I0_independent_heads','J1_joint_decoder')
def independent_decode(model,prediction):
 if prediction.no_boundary_probability>max(prediction.onset_distribution):return None
 step=max(range(len(prediction.onset_distribution)),key=lambda i:prediction.onset_distribution[i])+1;values=prediction.attribution_probabilities[step-1];return step,max(values,key=values.get)
def evaluate(split_name,sequences,onsets,reasons,models):
 rows=[]
 for method,model in models.items():
  predictions=[model.predict(seq) for seq in sequences];errors=[];exact=[];within=[];joint_exact=[];joint_within=[];safe_false=[];why_truth=[];why_pred=[]
  for onset,reason,prediction in zip(onsets,reasons,predictions):
   decoded=independent_decode(model,prediction) if method=='I0_independent_heads' else model.decode(prediction)
   if onset is None:safe_false.append(decoded is not None);continue
   error=abs(decoded[0]-onset) if decoded else 7;errors.append(error);exact.append(error==0);within.append(error<=1);joint_exact.append(decoded is not None and decoded==(onset,reason));joint_within.append(decoded is not None and abs(decoded[0]-onset)<=1 and decoded[1]==reason);why_truth.append(reason);why_pred.append({decoded[1]} if decoded else set())
  rows.append({'split':split_name,'method':method,'onset_mae':round(mean(errors),3),'exact_onset_accuracy':round(mean(exact),4),'within_1_onset_accuracy':round(mean(within),4),'decoded_attribution_macro_f1':round(macro_attr_f1(why_truth,why_pred),4),'joint_exact_accuracy':round(mean(joint_exact),4),'joint_within_1_accuracy':round(mean(joint_within),4),'safe_false_boundary_rate':round(mean(safe_false),4),'test_trajectories':len(sequences)})
 return rows
def write_csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def write_svg(path,rows):
 width,height=850,470;left,top,plot_h,plot_w=80,55,320,700;colors={'I0_independent_heads':'#2563eb','J1_joint_decoder':'#dc2626'};splits=('standard','cross_domain_gui');fields=(('joint_exact_accuracy','Joint exact'),('joint_within_1_accuracy','Joint ±1'),('safe_false_boundary_rate','Safe false boundary'));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">','<rect width="100%" height="100%" fill="white"/>','<text x="425" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Joint Temporal-Attribution Decoder</text>']
 for tick in range(6):v=tick/5;y=top+plot_h*(1-v);parts += [f'<line x1="{left}" y1="{y}" x2="{left+plot_w}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.1f}</text>']
 for fi,(field,label) in enumerate(fields):
  center=left+plot_w/3*(fi+.5);parts.append(f'<text x="{center}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="10">{label}</text>')
  for si,split_name in enumerate(splits):
   for mi,method in enumerate(METHODS):row=next(x for x in rows if x['split']==split_name and x['method']==method);value=float(row[field]);x=center+(si*2+mi-1.5)*34-13;y=top+plot_h*(1-value);opacity=1 if si else .55;parts.append(f'<rect x="{x}" y="{y}" width="26" height="{top+plot_h-y}" fill="{colors[method]}" opacity="{opacity}"/>')
 for i,method in enumerate(METHODS):x=150+i*330;parts += [f'<rect x="{x}" y="{height-36}" width="12" height="12" fill="{colors[method]}"/>',f'<text x="{x+17}" y="{height-26}" font-family="sans-serif" font-size="10">{method} (solid=GUI)</text>']
 parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')
def main():
 p=argparse.ArgumentParser();base=ROOT/'benchmarks/boundary_attribution';p.add_argument('--tasks',type=Path,default=base/'tasks.json');p.add_argument('--trajectories',type=Path,default=base/'trajectories.json');p.add_argument('--labels',type=Path,default=base/'attribution_labels.json');p.add_argument('--output',type=Path,default=ROOT/'results/joint_temporal_attribution.csv');p.add_argument('--plot',type=Path,default=ROOT/'results/joint_temporal_attribution.svg');a=p.parse_args();tasks={x['task_id']:x for x in json.loads(a.tasks.read_text())};trajectories=json.loads(a.trajectories.read_text());labels={x['trajectory_id']:x for x in json.loads(a.labels.read_text())};observable=[(x,sequence(tasks[x['task_id']]['task'],x)) for x in trajectories];rows=[]
 for name,predicate in (('standard',lambda x:split_standard(x['task_id'])),('cross_domain_gui',lambda x:tasks[x['task_id']]['domain'] in {'coding','web'})):
  train=[pair for pair in observable if predicate(pair[0])];test=[pair for pair in observable if not predicate(pair[0])];train_seq=[x[1] for x in train];onsets=[labels[x[0]['trajectory_id']]['boundary_step'] for x in train];reasons=[labels[x[0]['trajectory_id']]['attribution'] for x in train];independent=DelegationBoundaryAttributionModel();independent.fit(train_seq,onsets,reasons);joint=JointTemporalAttributionDecoder();joint.fit(train_seq,onsets,reasons);test_seq=[x[1] for x in test];test_on=[labels[x[0]['trajectory_id']]['boundary_step'] for x in test];test_reason=[labels[x[0]['trajectory_id']]['attribution'] for x in test];rows.extend(evaluate(name,test_seq,test_on,test_reason,{'I0_independent_heads':independent,'J1_joint_decoder':joint}))
 write_csv(a.output,rows);write_svg(a.plot,rows);print(json.dumps({'results':rows,'primary_metric':'joint_within_1_accuracy','decoder':'single softmax label space over none + four attribution reasons at each step','leakage_audit':'prediction receives observable sequence only'},indent=2))
if __name__=='__main__':main()
