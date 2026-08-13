#!/usr/bin/env python3
"""Experiment 3: history-horizon robustness and model memory."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.ldtd_contrastive_ablation import evaluate,load_pairs
def main():
 p=argparse.ArgumentParser();base=ROOT/"results/environment_influence_expansion";p.add_argument("--raw-dir",type=Path,default=base/"raw");p.add_argument("--output-dir",type=Path,default=base/"ldtd_horizon");a=p.parse_args();pairs=load_pairs(a.raw_dir);a.output_dir.mkdir(parents=True,exist_ok=True);rows=[];maximum=max(len(t["steps"]) for roles in pairs.values() for t in roles.values())
 for horizon in (5,10,20,50):
  model,result=evaluate(pairs,contrastive=True,history_window=horizon);artifact=a.output_dir/f"ldtd_horizon_{horizon}.json";model.save(artifact);rows.append({"history_horizon":horizon,"effective_horizon":min(horizon,maximum),"maximum_observed_trajectory_steps":maximum,"model_memory_kb":round(artifact.stat().st_size/1024,2),**result})
 with (a.output_dir/"horizon_robustness.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (a.output_dir/"horizon_robustness.json").write_text(json.dumps({"note":"20/50 truncate to the maximum observed trajectory length; they are robustness controls, not evidence about 50-step executions","results":rows},indent=2)+"\n");print(json.dumps(rows,indent=2))
if __name__=="__main__":main()
