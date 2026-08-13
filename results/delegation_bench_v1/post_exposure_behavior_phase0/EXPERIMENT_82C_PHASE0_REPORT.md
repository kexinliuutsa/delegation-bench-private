# Experiment 82C Phase 0 — Post-Exposure Behavioral Signal Audit

Status: **POST_EXPOSURE_BEHAVIOR_ANALYSIS_FEASIBLE**. This is a retrospective, exploratory, zero-rollout measurement-feasibility audit over the frozen DelegationBench v1 cohort. It does not estimate treatment, style, or PIDR associations.

## Recovery

Status: **RECOVERY_MEASUREMENT_FEASIBLE**. The deterministic seed-82030 sample contains 40 exposure-reached pairs; 33 (82.5%) are assessable and 33 have at least three post-divergence treatment steps. Strict recovery requires two consecutive matched control actions; relaxed recovery requires two consecutive matched capability states. The sample contains 1 strict and 6 relaxed candidates, with 7 unresolved. These are candidate measurements awaiting human validation, not outcome estimates.

## Adoption acknowledgment

Status: **ADOPTION_SIGNAL_TOO_SPARSE**. The un-enriched validation sample contains 60 exposure-reached decision points; only 0 preserve both explicit agent text and a subsequent action. The validation-sample-only provisional interface found 3 acknowledge-only, 0 acknowledge-and-adopt, 0 acknowledge-and-verify, 0 reject/question, and 57 unresolved cases. These are provisional rule outputs, not human gold. Tool-action strings were deliberately not treated as natural-language acknowledgment.

## Task-scope change

Status: **TASK_SCOPE_TEXT_TOO_SPARSE**. 0 trajectories preserve explicit framing both before and after exposure under the conservative text-only rule, below the required 60. Tool sequence length was not used as a proxy for scope.

## Firewalls and interpretation

Recovery does not imply safe behavior. Adoption does not imply successful attack. Scope expansion does not imply authority violation. Historical files were not modified; authority/D0 labels and PIDR values were not loaded. Identifier-only PIDR joinability is 100.0%. There are 28 reported endpoint cells with N < 5.
