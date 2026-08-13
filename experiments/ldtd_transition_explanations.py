#!/usr/bin/env python3
"""Experiment 1: nearest-normal transition evidence for LDTD alarms."""
from __future__ import annotations
import argparse,json,re,sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.ldtd_contrastive_ablation import evaluate,load_pairs
def main():
 p=argparse.ArgumentParser();base=ROOT/"results/environment_influence_expansion";p.add_argument("--raw-dir",type=Path,default=base/"raw");p.add_argument("--output",type=Path,default=base/"latent_delegation_transition/transition_explanations.json");a=p.parse_args();pairs=load_pairs(a.raw_dir);model,metrics=evaluate(pairs,contrastive=True);explanations=[]
 for pair,roles in sorted(pairs.items()):
  trajectory=roles["treatment"];previous=[];latent=None
  for event in trajectory["steps"]:
   score,observed=model.score_step(trajectory["task"],previous,event["observation"],event["action"],latent)
   if latent is not None and score>model.threshold:
    evidence=model.explain_transition(trajectory["task"],latent,observed,previous[-1],event["action"]);explanations.append({"pair_id":pair,"step":event["step"],"transition_surprise":round(score,6),"threshold":round(model.threshold,6),**evidence})
   latent=observed;previous.append(event["action"])
 report={"method":"cosine nearest normal transition retrieval","llm_used":False,"explanations":explanations,"alarm_count":len(explanations),"detector_metrics":metrics};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+"\n");print(json.dumps({"alarm_count":len(explanations),"output":str(a.output),"example":explanations[0] if explanations else None},indent=2))
if __name__=="__main__":main()

