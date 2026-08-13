#!/usr/bin/env python3
"""Experiment 19: learned compact memory for delegation transitions.

An event-level logistic model learns which observable events tend to precede a
delegation transition. M3 retains the top-k scored events. Evaluation current
states are inferred from observed prefixes; future oracle states are opened only
after every prediction has been produced.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from delegation_inference_baselines import FullHistoryRetrieval, observable_capability, sanitized_view, training_examples
from delegation_state_compression import HORIZONS, build_corpus
from learned_delegation_transition import DIMENSIONS, MultiLabelModel, Vocabulary, WeightedLogistic, delta_label, macro_f1
from models.delegation_state import DelegationState


TOP_K = 5
STOPWORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "into", "my", "of",
    "on", "the", "to", "under", "using", "with", "within",
}


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def task_relation(task: str, action: str, observation: str) -> tuple[str, float]:
    task_terms = set(words(task)) - STOPWORDS
    event_terms = set(words(action + " " + observation)) - STOPWORDS
    overlap = len(task_terms & event_terms)
    score = overlap / max(1, len(event_terms))
    relation = "strong" if score >= 0.25 else "weak" if overlap else "none"
    return relation, score


def observable_event(view: Any, index: int, current_step: int | None = None) -> dict[str, Any]:
    relation, relation_score = task_relation(view.task, view.actions[index], view.observations[index])
    value = {
        "source_step": index + 1,
        "action": view.actions[index],
        "action_capability": observable_capability(view.actions[index]),
        "observation_tokens": words(view.observations[index]),
        "task_relation": relation,
        "task_relation_score": round(relation_score, 4),
    }
    if current_step is not None:
        value["age"] = current_step - index - 1
    return value


def event_tokens(event: dict[str, Any]) -> set[str]:
    tokens = {f"capability:{event['action_capability']}", f"relation:{event['task_relation']}"}
    tokens.update(f"action:{token}" for token in words(event["action"]))
    tokens.update(f"observation:{token}" for token in event["observation_tokens"])
    return tokens


class EventImportanceModel:
    def __init__(self, documents: list[set[str]], labels: list[int]) -> None:
        self.vocabulary = Vocabulary(documents)
        transformed = [self.vocabulary.transform(document) for document in documents]
        self.model = WeightedLogistic(len(self.vocabulary.indices), epochs=38)
        self.model.fit(transformed, labels)

    def score(self, event: dict[str, Any]) -> float:
        features = self.vocabulary.transform(event_tokens(event))
        return self.model.sigmoid(self.model.bias + sum(self.model.weights[index] for index in features))


def build_importance_examples(training: list[dict[str, Any]]) -> tuple[list[set[str]], list[int]]:
    documents=[];labels=[]
    for sample in training:
        view=sanitized_view(sample)
        oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1,len(view.actions)):
            documents.append(event_tokens(observable_event(view,step-1)))
            labels.append(int(any(delta_label(oracle[step],oracle[step+1]))))
    return documents,labels


def selected_memory(view: Any, step: int, importance: EventImportanceModel) -> list[dict[str, Any]]:
    candidates=[]
    for index in range(step):
        event=observable_event(view,index,step)
        event["importance_score"]=round(importance.score(event),4)
        candidates.append(event)
    selected=sorted(candidates,key=lambda event:(event["importance_score"],event["source_step"]),reverse=True)[:TOP_K]
    return sorted(selected,key=lambda event:event["source_step"])


def payload(method: str, state: DelegationState, view: Any, step: int, importance: EventImportanceModel) -> dict[str, Any]:
    value:dict[str,Any]={"current_delegation_state":state.to_dict()}
    if method=="M0_current_state":
        return value
    value["task"]=view.task
    if method=="M1_last_5_events":
        value["events"]=[observable_event(view,index,step) for index in range(max(0,step-5),step)]
    elif method=="M2_full_trajectory":
        value["events"]=[observable_event(view,index,step) for index in range(step)]
    elif method=="M3_learned_memory":
        value["events"]=selected_memory(view,step,importance)
    else:
        raise ValueError(method)
    return value


def payload_tokens(value: dict[str, Any]) -> set[str]:
    tokens={f"state:{dimension}={state_value}" for dimension,state_value in value["current_delegation_state"].items()}
    if "task" in value:
        tokens.update(f"task:{token}" for token in words(value["task"]))
    for event in value.get("events",[]):
        age_bucket=min(int(event.get("age",0)),5)
        tokens.add(f"age:{age_bucket}")
        tokens.update(event_tokens(event))
    return tokens


METHODS=("M0_current_state","M1_last_5_events","M2_full_trajectory","M3_learned_memory")


def build_training_documents(training:list[dict[str,Any]],importance:EventImportanceModel)->tuple[dict[str,list[set[str]]],list[tuple[int,...]]]:
    documents={method:[] for method in METHODS};labels=[]
    for sample in training:
        view=sanitized_view(sample);oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
        for step in range(1,len(view.actions)):
            for method in METHODS:
                documents[method].append(payload_tokens(payload(method,oracle[step],view,step,importance)))
            labels.append(delta_label(oracle[step],oracle[step+1]))
    return documents,labels


def evaluate(evaluation:list[dict[str,Any]],state_model:FullHistoryRetrieval,importance:EventImportanceModel,models:dict[str,MultiLabelModel])->list[dict[str,Any]]:
    buckets={(method,horizon):{"labels":[],"predictions":[],"sizes":[],"full_sizes":[],"ages":[]} for method in METHODS for horizon in HORIZONS}
    for sample in evaluation:
        view=sanitized_view(sample);inferred=state_model.predict(view)
        predictions={method:[] for method in METHODS};sizes={method:[] for method in METHODS};ages={method:[] for method in METHODS};full_sizes=[]
        for step in range(1,len(view.actions)):
            full_value=payload("M2_full_trajectory",inferred[step],view,step,importance)
            full_sizes.append(len(json.dumps(full_value,separators=(",",":"),sort_keys=True).encode()))
            for method in METHODS:
                value=payload(method,inferred[step],view,step,importance)
                predictions[method].append(models[method].predict(payload_tokens(value)))
                sizes[method].append(len(json.dumps(value,separators=(",",":"),sort_keys=True).encode()))
                ages[method].extend(event.get("age",0) for event in value.get("events",[]))
        # Evaluation labels remain unavailable until all memory variants predict.
        oracle=[DelegationState.from_dict(value) for value in sample["oracle_states"]]
        labels=[delta_label(oracle[step],oracle[step+1]) for step in range(1,len(view.actions))]
        horizon=len(view.actions)
        for method in METHODS:
            bucket=buckets[(method,horizon)];bucket["labels"].extend(labels);bucket["predictions"].extend(predictions[method]);bucket["sizes"].extend(sizes[method]);bucket["full_sizes"].extend(full_sizes);bucket["ages"].extend(ages[method])
    rows=[]
    for method in METHODS:
        for horizon in HORIZONS:
            data=buckets[(method,horizon)]
            row={"method":method,"horizon":horizon,"transition_f1_macro":round(macro_f1(data["labels"],data["predictions"]),4)}
            for index,dimension in enumerate(DIMENSIONS):
                row[f"{dimension}_transition_accuracy"]=round(mean(label[index]==prediction[index] for label,prediction in zip(data["labels"],data["predictions"])),4)
            row["mean_serialized_memory_bytes"]=round(mean(data["sizes"]),1)
            row["compression_ratio_vs_full"]=round(mean(data["full_sizes"])/mean(data["sizes"]),3)
            row["mean_selected_event_age"]=round(mean(data["ages"]),2) if data["ages"] else ""
            row["prediction_events"]=len(data["labels"]);rows.append(row)
    return rows


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_svg(path:Path,rows:list[dict[str,Any]])->None:
    width,height=1040,570;left,right,top,bottom=75,35,55,75;panel_w=(width-left-right-50)/2;plot_h=height-top-bottom
    colors={"M0_current_state":"#64748b","M1_last_5_events":"#f59e0b","M2_full_trajectory":"#8b5cf6","M3_learned_memory":"#2563eb"};max_ratio=max(float(row["compression_ratio_vs_full"]) for row in rows);panels=(("transition_f1_macro","Transition macro F1",1.0),("compression_ratio_vs_full","Compression ratio",max_ratio));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<text x="520" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Learned delegation memory across horizons</text>']
    for panel,(field,title,scale) in enumerate(panels):
        x0=left+panel*(panel_w+50)
        for tick in range(6):
            fraction=tick/5;y=top+plot_h*(1-fraction);parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+panel_w}" y2="{y:.1f}" stroke="#e5e7eb"/>');parts.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{fraction*scale:.1f}</text>')
        parts.append(f'<text x="{x0+panel_w/2:.1f}" y="{top-12}" text-anchor="middle" font-family="sans-serif" font-size="14">{title}</text>')
        for method,color in colors.items():
            points=[]
            for index,horizon in enumerate(HORIZONS):
                row=next(value for value in rows if value["method"]==method and value["horizon"]==horizon);x=x0+panel_w*index/(len(HORIZONS)-1);y=top+plot_h*(1-float(row[field])/scale);points.append((x,y))
            parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            for x,y in points:parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        for index,horizon in enumerate(HORIZONS):
            x=x0+panel_w*index/(len(HORIZONS)-1);parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{horizon}</text>')
    for index,(method,color) in enumerate(colors.items()):
        x=left+index*235;parts.append(f'<rect x="{x}" y="{height-28}" width="12" height="12" fill="{color}"/>');parts.append(f'<text x="{x+17}" y="{height-18}" font-family="sans-serif" font-size="10">{method}</text>')
    parts.append('</svg>');path.parent.mkdir(parents=True,exist_ok=True);path.write_text("\n".join(parts),encoding="utf-8")


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=ROOT/"results/delegation_memory_results.csv");parser.add_argument("--plot",type=Path,default=ROOT/"results/delegation_memory_horizon.svg");args=parser.parse_args()
    training,evaluation=build_corpus();state_model=FullHistoryRetrieval(training_examples(training)[2]);importance_documents,importance_labels=build_importance_examples(training);importance=EventImportanceModel(importance_documents,importance_labels);documents,labels=build_training_documents(training,importance);models={method:MultiLabelModel(documents[method],labels,"logistic") for method in METHODS};rows=evaluate(evaluation,state_model,importance,models);write_csv(args.output,rows);write_svg(args.plot,rows)
    print(json.dumps({"training_trajectories":len(training),"evaluation_trajectories":len(evaluation),"top_k":TOP_K,"results":rows,"importance_positive_rate":round(mean(importance_labels),4),"oracle_isolation":"Importance uses training labels; evaluation memory selection and prediction use observable prefixes only."},indent=2))


if __name__=="__main__":main()
