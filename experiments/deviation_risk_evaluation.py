#!/usr/bin/env python3
"""Experiment 28: intent-conditioned delegation deviation evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
for entry in (ROOT,ROOT/'experiments'):
    if str(entry) not in sys.path:sys.path.insert(0,str(entry))

from models.deviation_risk_model import DeviationRiskModel
from models.risk_emergence_model import RiskEmergenceModel
from risk_emergence_learning import CDEMRiskModel,FrequencyModel,auroc,binary_f1,first_positive,sanitize,split_category,split_domain,split_standard,targets,training_arrays


METHODS=("M0_action","M1_capability","M2_delegation_state","M3_learned_risk_emergence","M4_deviation_risk")


def fit_models(training:list[dict[str,Any]])->dict[str,Any]:
    sequences,risk,onset=training_arrays(training)
    safe_sequences=[sanitize(sample['task'],sample['safe_trajectory']) for sample in training]
    models={'M0_action':FrequencyModel('action'),'M1_capability':FrequencyModel('capability'),'M2_delegation_state':FrequencyModel('state'),'M3_learned_risk_emergence':RiskEmergenceModel(),'M4_deviation_risk':DeviationRiskModel()}
    for name,model in models.items():
        if isinstance(model,FrequencyModel):model.fit(sequences,risk)
        elif isinstance(model,DeviationRiskModel):model.fit(safe_sequences,sequences,risk,onset)
        else:model.fit(sequences,risk,onset)
    return models


def expected_calibration_error(labels:list[int],scores:list[float],bins:int=10)->float:
    total=len(labels);error=0.0
    for index in range(bins):
        lower=index/bins;upper=(index+1)/bins
        members=[position for position,score in enumerate(scores) if lower<=score<(upper if index<bins-1 else upper+1e-12)]
        if members:
            confidence=mean(scores[position] for position in members);accuracy=mean(labels[position] for position in members);error+=len(members)/total*abs(confidence-accuracy)
    return error


def evaluate(split_name:str,testing:list[dict[str,Any]],models:dict[str,Any])->list[dict[str,Any]]:
    rows=[]
    for method,model in models.items():
        labels=[];scores=[];onset_errors=[];false_alarms=[]
        for sample in testing:
            for key in ('safe_trajectory','risky_trajectory'):
                trajectory=sample[key];sequence=sanitize(sample['task'],trajectory);prediction=model.predict(sequence)
                # Ground truth is opened only after inference on the sanitized sequence.
                risk,_=targets(trajectory);labels.extend(risk);scores.extend(prediction.risk_probabilities);binary=[int(value>=.5) for value in prediction.risk_probabilities]
                if key=='safe_trajectory':false_alarms.append(any(binary))
                else:
                    actual=int(trajectory['risk_onset_step']);candidate=max(range(len(prediction.onset_distribution)),key=lambda index:prediction.onset_distribution[index])+1
                    onset_errors.append(len(binary)+1 if prediction.no_onset_probability>max(prediction.onset_distribution) else abs(candidate-actual))
        predicted=[int(value>=.5) for value in scores]
        rows.append({'split':split_name,'method':method,'risk_detection_f1':round(binary_f1(labels,predicted),4),'auroc':round(auroc(labels,scores),4),'false_alarm_rate_safe_trajectories':round(mean(false_alarms),4),'ece_10_bin':round(expected_calibration_error(labels,scores),4),'mean_onset_localization_error':round(mean(onset_errors),3),'test_tasks':len(testing),'test_steps':len(labels)})
    return rows


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as handle:writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_svg(path:Path,rows:list[dict[str,Any]])->None:
    width,height=1100,610;left,top,bottom,gap,panel_w=75,60,80,55,455;plot_h=height-top-bottom;colors={'M0_action':'#64748b','M1_capability':'#f59e0b','M2_delegation_state':'#8b5cf6','M3_learned_risk_emergence':'#2563eb','M4_deviation_risk':'#dc2626'};splits=('standard','cross_domain_gui','risk_category_holdout');parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="550" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">Intent-conditioned delegation deviation</text>']
    for panel,(field,title) in enumerate((('risk_detection_f1','Risk detection F1'),('ece_10_bin','ECE (lower is better)'))):
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
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark',type=Path,default=ROOT/'benchmarks/risk_emergence/risk_emergence_v0.json');parser.add_argument('--output',type=Path,default=ROOT/'results/deviation_risk_evaluation.csv');parser.add_argument('--plot',type=Path,default=ROOT/'results/deviation_risk_evaluation.svg');args=parser.parse_args();samples=json.loads(args.benchmark.read_text(encoding='utf-8'));rows=[]
    for name,splitter in (('standard',split_standard),('cross_domain_gui',split_domain),('risk_category_holdout',split_category)):
        training,testing=splitter(samples);models=fit_models(training);rows.extend(evaluate(name,testing,models))
    write_csv(args.output,rows);write_svg(args.plot,rows);print(json.dumps({'results':rows,'deviation_model':'Intent-nearest safe envelope + learned deviation risk/onset heads','leakage_audit':'Inference receives only task/action/observation/capability/delegation_state; labels, category, and onset are excluded.'},indent=2))


if __name__=='__main__':main()
