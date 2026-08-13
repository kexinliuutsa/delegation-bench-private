#!/usr/bin/env python3
"""Experiment 30: evaluate risk-emergence boundary localization."""

from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from models.delegation_boundary_model import BoundaryPrediction,DelegationBoundaryModel
from models.risk_emergence_model import ObservableEvent,ObservableSequence
from risk_emergence_learning import auroc,binary_f1

METHODS=('B0_action_boundary','B1_capability_boundary','B2_delegation_delta','B3_learned_boundary')

def sequence(task:str,trajectory:dict[str,Any])->ObservableSequence:
    return ObservableSequence(task,tuple(ObservableEvent(step['action'],step['observation'],step['capability'],dict(step['delegation_state'])) for step in trajectory['steps']))

def split_task(task_id:str)->str:
    return 'train' if int(task_id.rsplit('_',1)[1])%10<7 else 'test'

def hazard(scores:list[float])->BoundaryPrediction:
    survival=1.0;distribution=[]
    for score in scores:distribution.append(survival*score);survival*=1-score
    total=sum(distribution)+survival
    return BoundaryPrediction(tuple(scores),tuple(value/total for value in distribution),survival/total)

class EmpiricalBoundaryModel:
    def __init__(self,kind:str)->None:self.kind=kind;self.counts={};self.prior=0.0
    def keys(self,sequence:ObservableSequence)->list[Any]:
        output=[];previous=None
        for event in sequence.events:
            if self.kind=='action':key=event.action.lower()
            elif self.kind=='capability':key=(previous.capability if previous else 'start',event.capability)
            else:
                key=tuple((dimension,previous.delegation_state[dimension] if previous else 'none',value) for dimension,value in sorted(event.delegation_state.items()) if previous is None or previous.delegation_state[dimension]!=value)
            output.append(key);previous=event
        return output
    def fit(self,sequences:list[ObservableSequence],onsets:list[int|None])->None:
        grouped=defaultdict(lambda:[0,0]);all_targets=[]
        for seq,onset in zip(sequences,onsets):
            for index,key in enumerate(self.keys(seq),1):target=int(index==onset);grouped[key][0]+=target;grouped[key][1]+=1;all_targets.append(target)
        self.counts=dict(grouped);self.prior=(sum(all_targets)+1)/(len(all_targets)+2)
    def predict(self,sequence:ObservableSequence)->BoundaryPrediction:
        scores=[]
        for key in self.keys(sequence):positive,total=self.counts.get(key,(0,0));scores.append((positive+1)/(total+2) if total else self.prior)
        return hazard(scores)

def fit_models(train_sequences:list[ObservableSequence],train_onsets:list[int|None])->dict[str,Any]:
    models={'B0_action_boundary':EmpiricalBoundaryModel('action'),'B1_capability_boundary':EmpiricalBoundaryModel('capability'),'B2_delegation_delta':EmpiricalBoundaryModel('state'),'B3_learned_boundary':DelegationBoundaryModel()}
    for model in models.values():model.fit(train_sequences,train_onsets)
    return models

def predicted_onset(prediction:BoundaryPrediction)->int|None:
    if prediction.no_boundary_probability>max(prediction.onset_distribution):return None
    return max(range(len(prediction.onset_distribution)),key=lambda index:prediction.onset_distribution[index])+1

def evaluate(split_name:str,test_sequences:list[ObservableSequence],test_onsets:list[int|None],models:dict[str,Any])->list[dict[str,Any]]:
    rows=[]
    for method,model in models.items():
        predictions=[model.predict(seq) for seq in test_sequences]  # fixed before labels are examined below
        truth_steps=[];scores=[];errors=[];exact=[];within=[];safe_alarms=[]
        for seq,onset,prediction in zip(test_sequences,test_onsets,predictions):
            truth=[int(onset==index) for index in range(1,len(seq.events)+1)];truth_steps.extend(truth);scores.extend(prediction.boundary_probabilities);choice=predicted_onset(prediction)
            if onset is None:safe_alarms.append(choice is not None)
            else:
                error=abs(choice-onset) if choice is not None else len(seq.events)+1;errors.append(error);exact.append(error==0);within.append(error<=1)
        decisions=[int(score>=.5) for score in scores]
        rows.append({'split':split_name,'method':method,'boundary_detection_f1':round(binary_f1(truth_steps,decisions),4),'boundary_auroc':round(auroc(truth_steps,scores),4),'mean_onset_localization_error':round(mean(errors),3),'exact_onset_accuracy':round(mean(exact),4),'within_1_step_accuracy':round(mean(within),4),'safe_trajectory_false_boundary_rate':round(mean(safe_alarms),4),'test_trajectories':len(test_sequences),'test_boundaries':sum(onset is not None for onset in test_onsets)})
    return rows

def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as handle:writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def write_svg(path:Path,rows:list[dict[str,Any]])->None:
    rows=[row for row in rows if row['split']=='cross_domain_gui']
    width,height=900,500;left,top,plot_h,plot_w=80,55,350,750;bar_w=38;group_w=plot_w/3;colors=['#64748b','#f59e0b','#2563eb','#dc2626'];metrics=(('boundary_detection_f1','Boundary F1'),('exact_onset_accuracy','Exact onset'),('safe_trajectory_false_boundary_rate','Safe false boundary'));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="450" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Risk Emergence Boundary Benchmark</text>']
    for tick in range(6):value=tick/5;y=top+plot_h*(1-value);parts += [f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>']
    for metric_index,(field,label) in enumerate(metrics):
        center=left+group_w*(metric_index+.5);parts.append(f'<text x="{center}" y="{top+plot_h+22}" text-anchor="middle" font-family="sans-serif" font-size="10">{label}</text>')
        for index,row in enumerate(rows):value=float(row[field]);x=center+(index-1.5)*(bar_w+8)-bar_w/2;y=top+plot_h*(1-value);parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{top+plot_h-y:.1f}" fill="{colors[index]}"/>')
    for index,row in enumerate(rows):x=70+index*205;parts += [f'<rect x="{x}" y="{height-36}" width="12" height="12" fill="{colors[index]}"/>',f'<text x="{x+17}" y="{height-26}" font-family="sans-serif" font-size="9">{row["method"]}</text>']
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')

def main()->None:
    parser=argparse.ArgumentParser();base=ROOT/'benchmarks/risk_boundary';parser.add_argument('--tasks',type=Path,default=base/'tasks.json');parser.add_argument('--trajectories',type=Path,default=base/'trajectories.json');parser.add_argument('--labels',type=Path,default=base/'risk_onset_labels.json');parser.add_argument('--output',type=Path,default=ROOT/'results/risk_boundary_evaluation.csv');parser.add_argument('--plot',type=Path,default=ROOT/'results/risk_boundary_evaluation.svg');args=parser.parse_args()
    tasks={item['task_id']:item for item in json.loads(args.tasks.read_text(encoding='utf-8'))};trajectories=json.loads(args.trajectories.read_text(encoding='utf-8'));labels={item['trajectory_id']:item for item in json.loads(args.labels.read_text(encoding='utf-8'))}
    observable=[(item,sequence(tasks[item['task_id']]['task'],item)) for item in trajectories];rows=[];split_sizes={}
    for split_name,predicate in (
        ('standard',lambda item:split_task(item['task_id'])=='train'),
        ('cross_domain_gui',lambda item:tasks[item['task_id']]['domain'] in {'coding','web'}),
    ):
        train=[pair for pair in observable if predicate(pair[0])];test=[pair for pair in observable if not predicate(pair[0])]
        train_sequences=[seq for _,seq in train];train_onsets=[labels[item['trajectory_id']]['risk_onset_step'] for item,_ in train];models=fit_models(train_sequences,train_onsets)
        test_sequences=[seq for _,seq in test];test_ids=[item['trajectory_id'] for item,_ in test]
        test_onsets=[labels[trajectory_id]['risk_onset_step'] for trajectory_id in test_ids]
        rows.extend(evaluate(split_name,test_sequences,test_onsets,models));split_sizes[split_name]={'train':len(train),'test':len(test)}
    write_csv(args.output,rows);write_svg(args.plot,rows);print(json.dumps({'splits':split_sizes,'results':rows,'research_object':'risk emergence localization, not final success or persistent risk classification','label_isolation':'onset labels are stored separately and never enter prediction sequences'},indent=2))

if __name__=='__main__':main()
