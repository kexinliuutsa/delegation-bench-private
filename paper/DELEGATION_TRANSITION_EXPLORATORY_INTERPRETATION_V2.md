# Experiment 79.1 — Abstention-Aware and Version-Disagreement Audit

**Retrospective/exploratory only.** This audit changes no predictions or historical Experiment 79 output.

## Coverage before accuracy

B0 and B1 produced determinate judgments at all 12 boundary steps, but full no-boundary trajectory coverage was 11.8% and 0.0%. Their selective 100% boundary results therefore do not establish population-level comparator performance. Abstention was never converted to NO_ALARM.

The recovered cohort contained only 12 contract-defined boundary events. Although all four monitors identified these events at the proposal step, contract-unaware baselines abstained on a large fraction of trajectories, substantially reducing the effective comparison sample. Moreover, static and transition-aware contract checks had identical first-boundary behavior by construction, while the collection provided limited post-boundary opportunities to assess state-tracking benefits. We therefore interpret the experiment as underpowered to distinguish the monitoring formulations, rather than as evidence that static contract checking is sufficient.

## Version disagreement

Global archived-vs-v2 capability agreement was 80.25%. Boundary-step agreement was 100.00%; first-boundary invariance was 100.00%. Boundary-changing disagreements: 0. Thus the disagreement is low at the evaluated boundary, despite lower global agreement.

## Post-boundary identification

All 12 boundary trajectories terminated at the sandbox boundary: 12; trajectories with post-boundary steps: 0; repeated-capability opportunities: 0. Static-check sufficiency is not established.

Recommendation: **REPLICATION_REQUIRES_DESIGN_REVISION**.
