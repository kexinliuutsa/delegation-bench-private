# Mapper v2 Readiness Metric Audit

## Decision

`READY_FOR_PHASE11_REEVALUATION`

This is a **metric-definition correction**, not a post-hoc performance rescue. The original metric counted correctly identified `unclassified` and `opaque_execution` actions as mapping failures, although the pilot protocol explicitly defines these as epistemic ABSTAIN states. No mapper rule, holdout example, split, gold annotation, contract, or diagnostic trajectory was changed.

## Why the metrics differ

Legacy coverage is 87.5% (42/48) because all six correct abstentions count as uncovered. Resolvable coverage conditions its denominator on the 42 holdout examples whose frozen gold sets are intended to be classifiable. It is 100.0%. Abstention quality is evaluated separately: precision 100.0%, recall 100.0%.

## Frozen holdout

- Resolvable: 42
- Abstention expected: 6
- Resolvable exact-set accuracy: 100.0%
- Resolvable micro F1: 1.0000
- Resolvable macro F1: 1.0000
- Selective accuracy: 100.0%
- Overall abstention rate: 12.5%

## Diagnostic read-only replay

- Global resolvable coverage: 100.0%
- Boundary-local resolvable coverage: 100.0%
- Diagnostic abstention rate: 0.0%

No DTM, action-risk, or task-alignment output was read.
