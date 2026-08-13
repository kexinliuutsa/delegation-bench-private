#!/usr/bin/env python3
"""Experiment 16: delegation-state sufficiency under trajectory compression.

M1 retains the task and complete event history. M2 performs online DEG updates
and retains only the current inferred state plus a bounded transition summary.
Training labels fit retrieval/transition models; evaluation labels are accessed
only after prediction.
"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from benchmarks.delegationbench.generate import STAGES, build_sample
from delegation_inference_baselines import (
    DelegationEvolutionGraph,
    FullHistoryRetrieval,
    PredictionView,
    Vectorizer,
    cosine,
    deep_size,
    sanitized_view,
    state_key,
    training_examples,
)
from models.delegation_state import DEFAULT_STATE, DelegationState, state_transition


HORIZONS = (5, 10, 20, 50)


def build_corpus() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    training=[]; evaluation=[]; index=1000
    names={5:"short",10:"medium",20:"long",50:"fifty"}
    for category in STAGES:
        for horizon in HORIZONS:
            for replicate in range(7):
                index += 1
                sample=build_sample(category,names[horizon],horizon,index)
                (training if replicate < 5 else evaluation).append(sample)
    return training,evaluation


class BinaryHistoryPredictor:
    """Nearest-neighbor next-transition forecast from full textual history."""

    def __init__(self, examples: list[tuple[str, bool]]) -> None:
        self.vectorizer=Vectorizer(document for document,_ in examples)
        self.examples=[(self.vectorizer.transform(document),label) for document,label in examples]
        self.priors=Counter(label for _,label in examples)

    def predict(self, document: str) -> bool:
        vector=self.vectorizer.transform(document)
        _,label=max(self.examples,key=lambda item:(cosine(vector,item[0]),self.priors[item[1]],item[1]))
        return label


def transition_summary(states: list[DelegationState]) -> dict[str, Any]:
    changed_dimensions: Counter[str]=Counter(); transition_count=0; last_dimensions:list[str]=[]; steps_since=0
    for previous,current in zip(states,states[1:]):
        delta=state_transition(previous,current)
        if delta["changed"]:
            transition_count += 1
            last_dimensions=sorted(delta["changes"])
            changed_dimensions.update(last_dimensions)
            steps_since=0
        else:
            steps_since += 1
    return {
        "steps_elapsed":len(states)-1,
        "transition_count":transition_count,
        "steps_since_transition":steps_since,
        "last_changed_dimensions":last_dimensions,
        "changed_dimension_counts":dict(sorted(changed_dimensions.items())),
    }


def compressed_feature(current: DelegationState, summary: dict[str, Any]) -> str:
    state_tokens=" ".join(f"state_{key}_{value}" for key,value in current.to_dict().items())
    dimensions=" ".join(f"changed_{key}_{value}" for key,value in summary["changed_dimension_counts"].items())
    last=" ".join(f"last_{value}" for value in summary["last_changed_dimensions"])
    return f"{state_tokens} transitions_{summary['transition_count']} since_{summary['steps_since_transition']} step_{summary['steps_elapsed']} {dimensions} {last}"


class BinaryCompressedPredictor:
    """Nearest-neighbor forecast using only D_t and transition summary."""

    def __init__(self, examples: list[tuple[str,bool]]) -> None:
        self.vectorizer=Vectorizer(document for document,_ in examples)
        self.examples=[(self.vectorizer.transform(document),label) for document,label in examples]
        self.priors=Counter(label for _,label in examples)

    def predict(self, current: DelegationState, summary: dict[str, Any]) -> bool:
        vector=self.vectorizer.transform(compressed_feature(current,summary))
        _,label=max(self.examples,key=lambda item:(cosine(vector,item[0]),self.priors[item[1]],item[1]))
        return label


def next_transition_examples(training:list[dict[str,Any]])->tuple[list[tuple[str,bool]],list[tuple[str,bool]]]:
    full=[];compressed=[]
    for sample in training:
        view=sanitized_view(sample)
        oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1,len(view.actions)):
            label=bool(state_transition(oracle[step],oracle[step+1])["changed"])
            full.append((FullHistoryRetrieval.document(view,step),label))
            compressed.append((compressed_feature(oracle[step],transition_summary(oracle[:step+1])),label))
    return full,compressed


def binary_f1(truth:list[bool],predicted:list[bool])->float:
    tp=sum(a and b for a,b in zip(truth,predicted));fp=sum(not a and b for a,b in zip(truth,predicted));fn=sum(a and not b for a,b in zip(truth,predicted))
    return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0


def serialize_full(view:PredictionView,step:int)->dict[str,Any]:
    return {"task":view.task,"history":[{"action":action,"observation":observation} for action,observation in zip(view.actions[:step],view.observations[:step])]}


def serialize_compressed(current:DelegationState,summary:dict[str,Any])->dict[str,Any]:
    return {"current_delegation_state":current.to_dict(),"transition_history_summary":summary}


def evaluate(evaluation:list[dict[str,Any]],full_state_model:FullHistoryRetrieval,deg:DelegationEvolutionGraph,full_next:BinaryHistoryPredictor,compressed_next:BinaryCompressedPredictor)->list[dict[str,Any]]:
    buckets:dict[tuple[str,int],dict[str,list[Any]]]=defaultdict(lambda:{"exact":[],"agreement":[],"transition_truth":[],"transition_pred":[],"serialized":[],"runtime":[],"full_serialized":[]})
    for sample in evaluation:
        view=sanitized_view(sample)
        # Complete both state prediction sequences before opening test labels.
        full_states=full_state_model.predict(view)
        compressed_states=deg.predict(view)
        full_next_predictions=[];compressed_next_predictions=[]
        for step in range(1,len(view.actions)):
            full_next_predictions.append(full_next.predict(FullHistoryRetrieval.document(view,step)))
            summary=transition_summary(compressed_states[:step+1])
            compressed_next_predictions.append(compressed_next.predict(compressed_states[step],summary))

        oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
        horizon=len(view.actions)
        for representation,states,next_predictions in (("M1_full_trajectory",full_states,full_next_predictions),("M2_delegation_state",compressed_states,compressed_next_predictions)):
            for step in range(1,len(view.actions)+1):
                full_payload=serialize_full(view,step)
                if representation=="M1_full_trajectory":
                    payload=full_payload
                    runtime_value=(view.task,view.actions[:step],view.observations[:step])
                else:
                    summary=transition_summary(states[:step+1])
                    payload=serialize_compressed(states[step],summary)
                    runtime_value=(states[step],summary,view.actions[step-1],view.observations[step-1])
                bucket=buckets[(representation,horizon)]
                bucket["exact"].append(states[step]==oracle[step])
                bucket["agreement"].append(states[step]==full_states[step])
                bucket["serialized"].append(len(json.dumps(payload,separators=(",",":"),sort_keys=True).encode()))
                bucket["full_serialized"].append(len(json.dumps(full_payload,separators=(",",":"),sort_keys=True).encode()))
                bucket["runtime"].append(deep_size(runtime_value))
                if step<len(view.actions):
                    bucket["transition_truth"].append(bool(state_transition(oracle[step],oracle[step+1])["changed"]))
                    bucket["transition_pred"].append(next_predictions[step-1])
    rows=[]
    for representation in ("M1_full_trajectory","M2_delegation_state"):
        for horizon in HORIZONS:
            data=buckets[(representation,horizon)]
            rows.append({
                "representation":representation,"horizon":horizon,
                "state_recovery_accuracy":round(mean(data["exact"]),4),
                "state_recovery_agreement_with_full":round(mean(data["agreement"]),4),
                "next_transition_f1":round(binary_f1(data["transition_truth"],data["transition_pred"]),4),
                "mean_serialized_memory_bytes":round(mean(data["serialized"]),1),
                "final_serialized_memory_bytes":max(data["serialized"]),
                "compression_ratio_vs_full":round(mean(data["full_serialized"])/mean(data["serialized"]),3),
                "final_compression_ratio_vs_full":round(max(data["full_serialized"])/max(data["serialized"]),3),
                "mean_runtime_context_bytes":round(mean(data["runtime"]),1),
                "evaluated_states":len(data["exact"]),
                "evaluated_next_transitions":len(data["transition_truth"]),
            })
    return rows


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_svg(path:Path,rows:list[dict[str,Any]])->None:
    width,height=1040,570;left,right,top,bottom=75,35,55,75;panel_w=(width-left-right-50)/2;plot_h=height-top-bottom
    colors={"M1_full_trajectory":"#8b5cf6","M2_delegation_state":"#2563eb"};parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="520" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation-state compression across horizons</text>']
    panels=(("state_recovery_accuracy","State recovery",1.0),("compression_ratio_vs_full","Compression ratio",max(float(r["compression_ratio_vs_full"]) for r in rows)))
    for panel,(field,title,scale) in enumerate(panels):
        x0=left+panel*(panel_w+50)
        for tick in range(6):
            fraction=tick/5;y=top+plot_h*(1-fraction);label=fraction*scale
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_w}" y2="{y:.1f}" stroke="#e5e7eb"/>');parts.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{label:.1f}</text>')
        parts.append(f'<text x="{x0+panel_w/2:.1f}" y="{top-12}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for representation,color in colors.items():
            points=[]
            for index,horizon in enumerate(HORIZONS):
                row=next(r for r in rows if r["representation"]==representation and r["horizon"]==horizon);x=x0+panel_w*index/(len(HORIZONS)-1);y=top+plot_h*(1-float(row[field])/scale);points.append((x,y))
            coords=" ".join(f"{x:.1f},{y:.1f}" for x,y in points);parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            for x,y in points:parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        for index,horizon in enumerate(HORIZONS):
            x=x0+panel_w*index/(len(HORIZONS)-1);parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index,(name,color) in enumerate(colors.items()):
        x=left+index*300;parts.append(f'<rect x="{x}" y="{height-28}" width="12" height="12" fill="{color}"/>');parts.append(f'<text x="{x+17}" y="{height-18}" font-family="sans-serif" font-size="11">{name}</text>')
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text("\n".join(parts),encoding="utf-8")


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=ROOT/"results/delegation_state_compression.csv");parser.add_argument("--plot",type=Path,default=ROOT/"results/delegation_state_compression.svg");args=parser.parse_args()
    training,evaluation=build_corpus();examples=training_examples(training);full_state_model=FullHistoryRetrieval(examples[2]);deg=DelegationEvolutionGraph(examples[3]);next_examples=next_transition_examples(training);full_next=BinaryHistoryPredictor(next_examples[0]);compressed_next=BinaryCompressedPredictor(next_examples[1])
    rows=evaluate(evaluation,full_state_model,deg,full_next,compressed_next);write_csv(args.output,rows);write_svg(args.plot,rows)
    print(json.dumps({"training_trajectories":len(training),"evaluation_trajectories":len(evaluation),"horizons":HORIZONS,"results":rows,"oracle_isolation":"Evaluation labels are opened only after state and next-transition predictions.","scope":"Representation sufficiency for delegation evolution; no safety classification."},indent=2))


if __name__=="__main__":main()
