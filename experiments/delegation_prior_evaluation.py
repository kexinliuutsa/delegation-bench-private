#!/usr/bin/env python3
"""Experiment 29: safe-only delegation-prior evaluation on GUI holdout."""

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

from deviation_risk_evaluation import expected_calibration_error
from models.delegation_prior_model import IntentConditionedDelegationPriorModel
from models.deviation_risk_model import DeviationRiskModel
from risk_emergence_learning import CDEMRiskModel,FrequencyModel,auroc,binary_f1,sanitize,split_domain,targets,training_arrays


METHODS=("M0_action","M1_capability","M2_cdem","M3_nn_envelope","M4_prior_deviation")


def fit_models(training:list[dict[str,Any]])->dict[str,Any]:
    sequences,risk,onset=training_arrays(training);safe=[sanitize(sample['task'],sample['safe_trajectory']) for sample in training]
    models={'M0_action':FrequencyModel('action'),'M1_capability':FrequencyModel('capability'),'M2_cdem':CDEMRiskModel(),'M3_nn_envelope':DeviationRiskModel(),'M4_prior_deviation':IntentConditionedDelegationPriorModel()}
    models['M0_action'].fit(sequences,risk);models['M1_capability'].fit(sequences,risk);models['M2_cdem'].fit(sequences,risk,onset);models['M3_nn_envelope'].fit(safe,sequences,risk,onset);models['M4_prior_deviation'].fit(safe)
    return models


def evaluate(testing:list[dict[str,Any]],models:dict[str,Any])->list[dict[str,Any]]:
    rows=[]
    for method,model in models.items():
        labels=[];scores=[];false_alarms=[];onset_errors=[]
        for sample in testing:
            for key in ('safe_trajectory','risky_trajectory'):
                trajectory=sample[key];sequence=sanitize(sample['task'],trajectory);prediction=model.predict(sequence)
                # Evaluation annotations are accessed only after model inference.
                risk,_=targets(trajectory);labels.extend(risk);scores.extend(prediction.risk_probabilities);decisions=[int(value>=.5) for value in prediction.risk_probabilities]
                if key=='safe_trajectory':false_alarms.append(any(decisions))
                else:
                    actual=int(trajectory['risk_onset_step']);candidate=max(range(len(prediction.onset_distribution)),key=lambda index:prediction.onset_distribution[index])+1
                    onset_errors.append(len(decisions)+1 if prediction.no_onset_probability>max(prediction.onset_distribution) else abs(candidate-actual))
        decisions=[int(value>=.5) for value in scores]
        rows.append({'split':'cross_domain_gui','method':method,'risk_detection_f1':round(binary_f1(labels,decisions),4),'auroc':round(auroc(labels,scores),4),'false_alarm_rate_safe_trajectories':round(mean(false_alarms),4),'ece_10_bin':round(expected_calibration_error(labels,scores),4),'mean_onset_localization_error':round(mean(onset_errors),3),'test_tasks':len(testing),'test_steps':len(labels)})
    return rows


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as handle:writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_svg(path:Path,rows:list[dict[str,Any]])->None:
    width,height=980,520;left,top,plot_h,plot_w=80,55,360,820;bar_w=28;group_w=plot_w/4;colors=['#64748b','#f59e0b','#2563eb','#8b5cf6','#dc2626'];metrics=(('risk_detection_f1','F1'),('auroc','AUROC'),('false_alarm_rate_safe_trajectories','Safe false alarm'),('ece_10_bin','ECE'));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="490" y="26" text-anchor="middle" font-family="sans-serif" font-size="18">Intent-conditioned delegation prior: GUI holdout</text>']
    for tick in range(6):value=tick/5;y=top+plot_h*(1-value);parts += [f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{value:.1f}</text>']
    for metric_index,(field,label) in enumerate(metrics):
        center=left+group_w*(metric_index+.5);parts.append(f'<text x="{center}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="10">{label}</text>')
        for method_index,row in enumerate(rows):value=float(row[field]);x=center+(method_index-2)*(bar_w+5)-bar_w/2;y=top+plot_h*(1-value);parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{top+plot_h-y:.1f}" fill="{colors[method_index]}"/>')
    for index,row in enumerate(rows):x=40+(index%3)*315;y=height-40+(index//3)*16;parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{colors[index]}"/>',f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="9">{row["method"]}</text>']
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts),encoding='utf-8')


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark',type=Path,default=ROOT/'benchmarks/risk_emergence/risk_emergence_v0.json');parser.add_argument('--output',type=Path,default=ROOT/'results/delegation_prior_evaluation.csv');parser.add_argument('--plot',type=Path,default=ROOT/'results/delegation_prior_evaluation.svg');args=parser.parse_args();samples=json.loads(args.benchmark.read_text(encoding='utf-8'));training,testing=split_domain(samples);models=fit_models(training);rows=evaluate(testing,models);write_csv(args.output,rows);write_svg(args.plot,rows)
    prior=models['M4_prior_deviation'];example=sanitize(testing[0]['task'],testing[0]['safe_trajectory']);print(json.dumps({'training_domains':['coding','web'],'testing_domain':'GUI','training_safe_trajectories':len(training),'results':rows,'example_expected_prior':[{'capabilities':item.expected_capability_probabilities,'expected_set':sorted(item.expected_capability_set),'state_ranks':item.expected_state_ranks} for item in prior.expected_delegation_prior(example)],'leakage_audit':'M4 fit accepts safe observable sequences only; inference receives no annotations.'},indent=2))


if __name__=='__main__':main()
