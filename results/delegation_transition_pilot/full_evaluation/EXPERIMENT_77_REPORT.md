# Experiment 77 — Delegation Transition Full Evaluation

## Preregistered QC decision

`GROUND_TRUTH_OR_MAPPER_INSUFFICIENT`

All 40 pairs / 80 real trajectories are complete, schema-valid, and generation-isolated. Contract leakage is zero; proposal ordering, monitor-input equality, and sandbox integrity are 100%. However, the frozen mapper returned `unclassified` on four substantive proposed actions. Consequently, four trajectories have unresolved contract-boundary status. The preregistered hard gate requires zero unresolved boundaries, so comparative DTM/B0/B1 performance metrics were **not evaluated or reported**.

- global resolvable coverage: 98.99%
- boundary-local resolvable coverage: 98.00%
- unresolved trajectories: 4

No mapper, contract, monitor, baseline, boundary definition, rollout, or inclusion rule was changed.
