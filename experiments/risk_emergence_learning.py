#!/usr/bin/env python3
"""Learned evaluation for Risk Emergence Model v1."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
for entry in (ROOT,ROOT/'experiments'):
    if str(entry) not in sys.path:sys.path.insert(0,str(entry))

from context_delegation_evolution import ExecutionContextState, context_tokens
from learned_delegation_transition import Vocabulary, WeightedLogistic
from models.delegation_state import DelegationState
from models.risk_emergence_model import ObservableEvent, ObservableSequence, RiskEmergenceModel, RiskPrediction
from trigger_delegation_model import TriggerState


METHODS=("M0_action_frequency","M1_capability_model","M2_delegation_state_model","M3_cdem","M4_learned_risk_emergence")


def sanitize(task:str,trajectory:dict[str,Any])->ObservableSequence:
    return ObservableSequence(task,tuple(ObservableEvent(step['action'],step['observation'],step['capability'],dict(step['delegation_state'])) for step in trajectory['steps']))


def targets(trajectory:dict[str,Any])->tuple[list[int],list[int]]:
    risk=[int(step['risk_label']=='risk_emerged') for step in trajectory['steps']]
    onset=[0]*len(risk)
    if trajectory['risk_onset_step'] is not None:onset[int(trajectory['risk_onset_step'])-1]=1
    return risk,onset


def hazard_distribution(probabilities:list[float])->tuple[tuple[float,...],float]:
    survival=1.0;values=[]
    for probability in probabilities:
        hazard=max(0.0,min(1.0,probability));values.append(survival*hazard);survival*=1-hazard
    total=sum(values)+survival
    return tuple(value/total for value in values),survival/total


class FrequencyModel:
    def __init__(self,kind:str)->None:self.kind=kind;self.counts:dict[Any,list[int]]={};self.prior=0.5
    def key(self,event:ObservableEvent)->Any:
        if self.kind=='action':return event.action.lower()
        if self.kind=='capability':return event.capability
        return tuple(sorted(event.delegation_state.items()))
    def fit(self,sequences:list[ObservableSequence],labels:list[list[int]])->None:
        grouped=defaultdict(lambda:[0,0]);all_values=[]
        for sequence,values in zip(sequences,labels):
            for event,label in zip(sequence.events,values):grouped[self.key(event)][0]+=label;grouped[self.key(event)][1]+=1;all_values.append(label)
        self.counts=dict(grouped);self.prior=(sum(all_values)+1)/(len(all_values)+2)
    def predict(self,sequence:ObservableSequence)->RiskPrediction:
        probabilities=[]
        for event in sequence.events:
            positive,total=self.counts.get(self.key(event),(0,0));probabilities.append((positive+1)/(total+2) if total else self.prior)
        distribution,no_onset=hazard_distribution(probabilities);return RiskPrediction(tuple(probabilities),distribution,no_onset)


def cdem_documents(sequence:ObservableSequence)->list[set[str]]:
    class View:
        task=sequence.task
    context=ExecutionContextState(sequence.task);flat=TriggerState();documents=[]
    for event in sequence.events:
        flat.update(event.action,event.observation);context.update(event.action,event.observation)
        documents.append(context_tokens(DelegationState.from_dict(event.delegation_state),flat,context))
    return documents


class CDEMRiskModel:
    def __init__(self)->None:self.vocabulary:Vocabulary|None=None;self.risk:WeightedLogistic|None=None;self.onset:WeightedLogistic|None=None
    def fit(self,sequences:list[ObservableSequence],risk_targets:list[list[int]],onset_targets:list[list[int]])->None:
        documents=[];risk=[];onset=[]
        for sequence,risk_values,onset_values in zip(sequences,risk_targets,onset_targets):documents.extend(cdem_documents(sequence));risk.extend(risk_values);onset.extend(onset_values)
        self.vocabulary=Vocabulary(documents);features=[self.vocabulary.transform(document) for document in documents]
        self.risk=WeightedLogistic(len(self.vocabulary.indices),epochs=45);self.risk.fit(features,risk)
        self.onset=WeightedLogistic(len(self.vocabulary.indices),epochs=45);self.onset.fit(features,onset)
    def predict(self,sequence:ObservableSequence)->RiskPrediction:
        if self.vocabulary is None or self.risk is None or self.onset is None:raise RuntimeError('model not fitted')
        features=[self.vocabulary.transform(document) for document in cdem_documents(sequence)]
        risk=tuple(self.risk.sigmoid(self.risk.bias+sum(self.risk.weights[i] for i in value)) for value in features)
        hazards=[self.onset.sigmoid(self.onset.bias+sum(self.onset.weights[i] for i in value)) for value in features]
        distribution,no_onset=hazard_distribution(hazards);return RiskPrediction(risk,distribution,no_onset)


def split_standard(samples:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    training=[];testing=[]
    for sample in samples:
        number=int(sample['id'].rsplit('_',1)[1]);(training if number%10<7 else testing).append(sample)
    return training,testing


def split_domain(samples:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    return [sample for sample in samples if sample['domain'] in {'coding','web'}],[sample for sample in samples if sample['domain']=='GUI']


def split_category(samples:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    training_categories={'unnecessary authority expansion','unnecessary data access'}
    return [sample for sample in samples if sample['risky_trajectory']['risk_category'] in training_categories],[sample for sample in samples if sample['risky_trajectory']['risk_category'] not in training_categories]


def training_arrays(samples:list[dict[str,Any]])->tuple[list[ObservableSequence],list[list[int]],list[list[int]]]:
    sequences=[];risk=[];onset=[]
    for sample in samples:
        for key in ('safe_trajectory','risky_trajectory'):
            sequences.append(sanitize(sample['task'],sample[key]));risk_values,onset_values=targets(sample[key]);risk.append(risk_values);onset.append(onset_values)
    return sequences,risk,onset


def fit_models(training:list[dict[str,Any]])->dict[str,Any]:
    sequences,risk,onset=training_arrays(training);models={
        'M0_action_frequency':FrequencyModel('action'),'M1_capability_model':FrequencyModel('capability'),'M2_delegation_state_model':FrequencyModel('state'),'M3_cdem':CDEMRiskModel(),'M4_learned_risk_emergence':RiskEmergenceModel(),
    }
    for model in models.values():model.fit(sequences,risk,onset) if not isinstance(model,FrequencyModel) else model.fit(sequences,risk)
    return models


def auroc(labels:list[int],scores:list[float])->float:
    positives=[score for label,score in zip(labels,scores) if label];negatives=[score for label,score in zip(labels,scores) if not label]
    if not positives or not negatives:return float('nan')
    wins=sum(p>n for p in positives for n in negatives)+0.5*sum(p==n for p in positives for n in negatives)
    return wins/(len(positives)*len(negatives))


def binary_f1(truth:list[int],predicted:list[int])->float:
    tp=sum(a==1 and b==1 for a,b in zip(truth,predicted));fp=sum(a==0 and b==1 for a,b in zip(truth,predicted));fn=sum(a==1 and b==0 for a,b in zip(truth,predicted));return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0


def first_positive(values:list[int])->int|None:return next((index for index,value in enumerate(values,1) if value),None)


def evaluate(split_name:str,testing:list[dict[str,Any]],models:dict[str,Any])->list[dict[str,Any]]:
    rows=[]
    for method,model in models.items():
        labels=[];scores=[];onset_errors=[];delays=[];false_alarms=[];risky_detected=[]
        for sample in testing:
            for key in ('safe_trajectory','risky_trajectory'):
                trajectory=sample[key];sequence=sanitize(sample['task'],trajectory);prediction=model.predict(sequence)
                # Labels and onset are evaluation-only and accessed after prediction.
                risk,_=targets(trajectory);binary=[int(value>=.5) for value in prediction.risk_probabilities]
                labels.extend(risk);scores.extend(prediction.risk_probabilities)
                if key=='safe_trajectory':false_alarms.append(any(binary))
                else:
                    actual=int(trajectory['risk_onset_step']);detected=first_positive(binary);risky_detected.append(detected is not None)
                    onset_choice=max(range(len(prediction.onset_distribution)),key=lambda index:prediction.onset_distribution[index])+1
                    if prediction.no_onset_probability>max(prediction.onset_distribution):onset_errors.append(len(binary)+1)
                    else:onset_errors.append(abs(onset_choice-actual))
                    delays.append(detected-actual if detected is not None else len(binary)+1)
        predicted=[int(value>=.5) for value in scores]
        rows.append({'split':split_name,'method':method,'risk_detection_f1':round(binary_f1(labels,predicted),4),'auroc':round(auroc(labels,scores),4),'mean_onset_localization_error':round(mean(onset_errors),3),'mean_detection_delay':round(mean(delays),3),'false_alarm_rate_safe_trajectories':round(mean(false_alarms),4),'risky_trajectory_detection_rate':round(mean(risky_detected),4),'test_tasks':len(testing),'test_steps':len(labels)})
    return rows


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as handle:writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_svg(path:Path,rows:list[dict[str,Any]])->None:
    width,height=1100,610;left,top,bottom,gap,panel_w=75,60,80,55,455;plot_h=height-top-bottom;colors={'M0_action_frequency':'#64748b','M1_capability_model':'#f59e0b','M2_delegation_state_model':'#8b5cf6','M3_cdem':'#2563eb','M4_learned_risk_emergence':'#dc2626'};splits=('standard','cross_domain_gui','risk_category_holdout');parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="550" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">Learned risk emergence evaluation</text>']
    for panel,(field,title) in enumerate((('risk_detection_f1','Risk detection F1'),('auroc','AUROC'))):
        x0=left+panel*(panel_w+gap)
        for tick in range(6):value=tick/5;y=top+plot_h*(1-value);parts += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_w}" y2="{y:.1f}" stroke="#e5e7eb"/>',f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>']
        parts.append(f'<text x="{x0+panel_w/2}" y="{top-13}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method,color in colors.items():
            points=[]
            for index,split in enumerate(splits):row=next(item for item in rows if item['method']==method and item['split']==split);x=x0+panel_w*index/(len(splits)-1);y=top+plot_h*(1-float(row[field]));points.append((x,y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>');parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>' for x,y in points)
        for index,split in enumerate(splits):x=x0+panel_w*index/(len(splits)-1);parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="10">{split}</text>')
    for index,(method,color) in enumerate(colors.items()):x=65+(index%3)*340;y=height-40+(index//3)*16;parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{color}"/>',f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="9">{method}</text>']
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark',type=Path,default=ROOT/'benchmarks/risk_emergence/risk_emergence_v0.json');parser.add_argument('--output',type=Path,default=ROOT/'results/risk_emergence_learning.csv');parser.add_argument('--plot',type=Path,default=ROOT/'results/risk_emergence_learning.svg');args=parser.parse_args();samples=json.loads(args.benchmark.read_text(encoding='utf-8'));rows=[]
    for name,splitter in (('standard',split_standard),('cross_domain_gui',split_domain),('risk_category_holdout',split_category)):
        training,testing=splitter(samples);models=fit_models(training);rows.extend(evaluate(name,testing,models))
    write_csv(args.output,rows);write_svg(args.plot,rows);print(json.dumps({'results':rows,'model':'256-dimensional recurrent hashed encoder with risk and onset heads','leakage_audit':'Inference sequences contain task/action/observation/capability/delegation_state only; split metadata and labels are excluded.'},indent=2))


if __name__=='__main__':main()
