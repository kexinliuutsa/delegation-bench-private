#!/usr/bin/env python3
"""Experiment 68: audit aggregation-rule selection and evaluation reuse."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'results/protocol_validity');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
 source=ROOT/'results/multi_agent_delegation/pibr_oof_threshold_diagnostics/pair_aggregation/aggregation_results.csv';prior=list(csv.DictReader(source.open()));rows=[]
 for item in prior:
  rule=item['aggregation'];is_mean=rule=='mean';rows.append({'representation':item['representation'],'aggregation_rule':rule,'selection_dataset_split':'pooled three-fold OOF Web pairs (48); rules compared post hoc','final_reporting_dataset_split':'same pooled three-fold OOF Web pairs (48)','auroc':item['trajectory_auroc_control_vs_treatment'],'same_pairs_reused':True,'pre_specified':False,'classification':'EXPLORATORY','status':'EXPLORATORY_SELECTION_BIAS_RISK' if is_mean else 'EXPLORATORY_RULE_COMPARISON','evidence_file':str(source.relative_to(ROOT))})
 # The equal-length result is a sensitivity analysis discovered after inspecting
 # the same Web pairs, not a new confirmatory holdout.
 confound=ROOT/'results/multi_agent_delegation/pibr_mean_confound_audit/length_controlled_mean_results.csv'
 for item in csv.DictReader(confound.open()):
  if item['subset']=='equal_length_pairs_only':
   rows.append({'representation':'PIBR_transition_kNN','aggregation_rule':'mean_equal_length_sensitivity','selection_dataset_split':'same Web 48-pair audit; equal-length subset identified post hoc','final_reporting_dataset_split':'32 equal-length Web pairs drawn from same evaluation pool','auroc':item['trajectory_auroc'],'same_pairs_reused':True,'pre_specified':False,'classification':'EXPLORATORY','status':'EXPLORATORY_SELECTION_BIAS_RISK','evidence_file':str(confound.relative_to(ROOT))})
 with (a.output_dir/'aggregation_selection_audit.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 tested=sorted({x['aggregation_rule'] for x in rows});summary={'rules_discovered':tested,'source_files':[str(source.relative_to(ROOT)),str(confound.relative_to(ROOT))],'current_mean_aggregation_status':'EXPLORATORY_SELECTION_BIAS_RISK','confirmatory_results':0,'exploratory_results':len(rows),'same_evaluation_pairs_used_for_rule_comparison_and_reporting':True,'new_untouched_holdout_required_for_confirmatory_mean_claim':True};(a.output_dir/'aggregation_selection_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
