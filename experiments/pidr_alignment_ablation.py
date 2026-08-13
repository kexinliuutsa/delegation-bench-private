#!/usr/bin/env python3
"""Experiment 64: ablate PIDR's benign cross-paradigm alignment loss."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experiments.cross_domain_monitor_transfer import load
from experiments.paradigm_invariant_delegation_representation import decorate,intervention_pairs,ordered,progress_pairs,representation_metrics,retrieval_eval
from models.paradigm_invariant_delegation import ParadigmInvariantDelegationRepresentation

def main():
 p=argparse.ArgumentParser();base=ROOT/'results/multi_agent_delegation';p.add_argument('--rollouts',type=Path,default=base/'normalized_rollouts.jsonl');p.add_argument('--pidr-summary',type=Path,default=base/'pidr/summary.json');p.add_argument('--output-dir',type=Path,default=base/'pidr_alignment_ablation');a=p.parse_args();cohorts=load(a.rollouts);decorate(cohorts);coding=cohorts['gpt5_minimal_coding_agent'];web=cohorts['gpt5_minimal_web_agent'];positives=[]
 for seed in (0,1):positives+=progress_pairs(ordered(coding,seed),ordered(web,seed))
 negatives=intervention_pairs(coding,{0,1})+intervention_pairs(web,{0,1});no_alignment=ParadigmInvariantDelegationRepresentation();no_alignment.fit([],negatives);benign,separation,ratio=representation_metrics(no_alignment,coding,web);no_align_row={'method':'B1_PIDR_no_alignment','cross_benign_distance':round(benign,6),'intervention_separation':round(separation,6),'separation_alignment_ratio':round(ratio,4),**retrieval_eval(no_alignment,coding,web)}
 prior=json.loads(a.pidr_summary.read_text())['results'];raw=next(dict(x) for x in prior if x['method']=='B1_raw_action_encoder');raw['method']='B0_raw_encoder';full=next(dict(x) for x in prior if x['method']=='B2_PIDR');full['method']='B2_PIDR_full';rows=[raw,no_align_row,full];a.output_dir.mkdir(parents=True,exist_ok=True);no_alignment.save(a.output_dir/'pidr_no_alignment_model.json')
 with (a.output_dir/'alignment_ablation.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 report={'experiment':64,'changed_variable':'presence of cross-paradigm benign alignment pairs','fixed':{'encoder':True,'initialization_seed':63,'margin':0.45,'training_seeds':[0,1],'heldout_seed':2,'negative_pair_count':len(negatives),'threshold_calibration':'leave-one-coding-control-out'},'positive_pair_count_full':len(positives),'positive_pair_count_no_alignment':0,'interpretation_limit':'This establishes the contribution of the alignment loss. It does not by itself prove that matched alignment pairs are free of task-semantic signal.','results':rows};(a.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
