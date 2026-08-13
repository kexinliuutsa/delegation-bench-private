#!/usr/bin/env python3
"""Experiment 68: combine protocol validity and robustness audit artifacts."""
from __future__ import annotations
import argparse,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=ROOT/'results/protocol_validity');a=p.parse_args()
 generation=json.loads((a.input_dir/'generation_isolation_summary.json').read_text());bootstrap=json.loads((a.input_dir/'pair_bootstrap_summary.json').read_text());selection=json.loads((a.input_dir/'aggregation_selection_summary.json').read_text())
 supported=generation['causal_trajectory_level_claim_supported']
 conclusion=('Current protocol supports a trajectory-level randomized intervention-effect claim, but not a within-trajectory temporal drift-onset claim.' if supported else 'Current protocol does not support a clean intervention-effect claim because unexpected pre-treatment generation differences were found.')
 # The mandated B wording is retained when verification fails; clarify whether
 # failure is an observed mismatch or unavailable provenance rather than hiding it.
 reason=('fully verified' if supported else ('observed unexpected difference' if generation['pairs_with_unexpected_pre_treatment_difference'] else 'required pre-treatment generation metadata is UNKNOWN'))
 def result(rep,subset):return next(x for x in bootstrap['results'] if x['representation']==rep and x['dataset_subset']==subset)
 def delta(rep):return next(x for x in bootstrap['delta_auroc'] if x['representation']==rep)
 primary=result('PIBR_transition_kNN','web_full_48');equal=result('PIBR_transition_kNN','web_equal_length_32');change=delta('PIBR_transition_kNN')
 report={'experiment':68,'conclusion':conclusion,'conclusion_reason':reason,'binary_conclusion_qualification':'No known unexpected difference was observed; conclusion B is selected because mandatory generation fields are UNKNOWN, which prevents full verification.','generation_isolation':generation,'trajectory_length_role':'POST_TREATMENT_MEDIATOR_OR_OUTCOME; not classified as a pre-treatment generation confounder','statistical_uncertainty':bootstrap,'primary_pibr_mean_result':primary,'equal_length_sensitivity':equal,'delta_full_minus_equal':change,'aggregation_selection':selection,'sample_sizes':{'coding_pairs_generation_audit':48,'web_pairs_generation_audit':48,'web_pairs_full_statistics':48,'web_pairs_equal_length_statistics':32},'claim_boundary':{'trajectory_level_intervention_effect':supported,'within_trajectory_temporal_onset':False,'delegation_or_authority_ground_truth':False,'maliciousness_or_unsafe_action':False},'mutations':{'trajectories_modified':False,'pidr_weights_modified':False,'thresholds_tuned':False,'new_rollouts_generated':False}}
 (a.input_dir/'protocol_validity_report.json').write_text(json.dumps(report,indent=2)+'\n')
 md=f'''# Experiment 68: Protocol Validity and Statistical Robustness Audit

## Conclusion

**{conclusion}**

Reason: {reason}. Persisted manifests and integrity audits show no known extra initial-state differences beyond declared intervention artifacts, but missing runtime snapshots remain `UNKNOWN`; equality is not inferred from current source code.

## Generation isolation

- Fully clean/verified pairs: {generation['clean_pairs']}/{generation['total_pairs']}
- Known unexpected pre-treatment differences: {generation['pairs_with_unexpected_pre_treatment_difference']}
- Pairs with required UNKNOWN fields: {generation['pairs_with_unknown_generation_fields']}
- Trajectory-level causal claim supported: {str(supported).lower()}
- Within-trajectory onset claim supported: false

Trajectory length, action count, tool counts, and final state are treated as post-treatment outcomes or potential mediators—not generation confounders.

## Pair-level uncertainty

| Analysis | Pairs | AUROC | Pair-bootstrap 95% CI | SE |
|---|---:|---:|---:|---:|
| PIBR mean, full Web | {primary['pairs']} | {primary['auroc']:.4f} | [{primary['bootstrap_ci_low']:.4f}, {primary['bootstrap_ci_high']:.4f}] | {primary['bootstrap_standard_error']:.4f} |
| PIBR mean, equal-length Web | {equal['pairs']} | {equal['auroc']:.4f} | [{equal['bootstrap_ci_low']:.4f}, {equal['bootstrap_ci_high']:.4f}] | {equal['bootstrap_standard_error']:.4f} |

Full minus equal-length AUROC: {change['delta_point_estimate']:.4f}, 95% CI [{change['bootstrap_ci_low']:.4f}, {change['bootstrap_ci_high']:.4f}], P(delta > 0) = {change['probability_delta_gt_0']:.4f}.

All 10,000 replicates resample complete control/treatment pairs. No individual steps are independently bootstrapped. A comparable Coding OOF pair-score file was unavailable, so no Coding AUROC was invented.

## Aggregation selection

Current mean aggregation status: **{selection['current_mean_aggregation_status']}**. Mean was selected after comparing multiple aggregation rules on the same 48 Web pairs used for reporting. It is exploratory, not confirmatory. A genuinely untouched holdout is required for a confirmatory aggregation claim.

## Claim boundary

This audit makes no causal claim beyond the persisted generation evidence. It does not support temporal drift onset, delegation/authority ground truth, maliciousness, unsafe-action detection, or unseen-paradigm generalization.
'''
 (a.input_dir/'protocol_validity_report.md').write_text(md);print(json.dumps({'conclusion':conclusion,'clean_pairs':f"{generation['clean_pairs']}/{generation['total_pairs']}",'full_auroc':primary,'equal_length_auroc':equal,'delta':change,'aggregation_status':selection['current_mean_aggregation_status']},indent=2))
if __name__=='__main__':main()
