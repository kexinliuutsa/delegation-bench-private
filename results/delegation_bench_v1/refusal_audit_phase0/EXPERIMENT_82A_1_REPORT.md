# Experiment 82A.1 — Refusal Rule Validation

This is a synthetic diagnostic challenge, not a benchmark outcome analysis. It used no rollouts, model calls, PIDR values, or treatment/control comparison. The frozen v1 classifier (`fc4752a5961918617ca1c0110e844a3e20a45e0601ea11e858f0de491cfa1d83`) was evaluated once after the 80-example challenge set was frozen (`b904ef1b3b65f8909842b432be984e9a2dbee5a133176a860ce6688b50a0bc42`).

## Results

- Accuracy: 42.5%
- Macro F1: 0.384
- REFUSE recall: 53.3%
- REQUEST_CONFIRMATION recall: 33.3%
- HESITATE recall: 26.7%
- Hard-negative specificity: 76.9% (N=26)
- ABSTAIN precision / recall: 0.0% / 0.0%

Final status: **RULE_SPECIFICITY_INSUFFICIENT**.

The classifier's synthetic behavior does not establish recall on real trajectories. Historical Phase-0 labels were not modified. The separate conservative real-sample sanity review found 0 clear refusal, 0 clear confirmation-request, and 0 clear hesitation misses; this narrow check is not human annotation or an accuracy estimate.
