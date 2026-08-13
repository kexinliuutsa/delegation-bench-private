# Experiment 79 — Recovered Exploratory Comparison

**RETROSPECTIVE / EXPLORATORY — RETROSPECTIVE_EXPLORATORY_AFTER_NORMALIZER_V2_REPAIR**

Normalizer v2 was developed after a schema-coverage failure was identified on this cohort. Therefore all method comparisons on the recovered Experiment-77 trajectories are exploratory and cannot serve as an independent confirmatory test.

Experiment 77 permanently remains `GROUND_TRUTH_OR_MAPPER_INSUFFICIENT`. This analysis used Normalizer v2 only for ground-truth reconstruction and extracted the original archived pre-execution DTM/B0/B1 outputs.

## Results

| Method | Detection | False alarm | Exact | ±1 | Mean lead | Pair consistency |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 1.000 | 0.000 | 1.000 | 1.000 | 0 | 1.000 |
| B1 | 1.000 | 0.000 | 1.000 | 1.000 | 0 | 1.000 |
| B2 | 1.000 | 0.000 | 1.000 | 1.000 | 0 | 1.000 |
| DTM | 1.000 | 0.000 | 1.000 | 1.000 | 0 | 1.000 |

B2 is a post-Experiment-77 exploratory static contract checker. DTM and B2 see frozen D0; B0 and B1 do not. The comparison therefore asks whether explicit delegation-contract information adds value over contract-unaware judgments, not which architecture is generically superior. Ground truth uses D0 + Normalizer v2 + Mapper v2, while DTM used D0 + frozen runtime mappings. Capability agreement was 0.802; 11 boundary trajectories were definitionally forced exact matches under identical mappings.

Lead zero means detection on the proposed boundary action before execution, not early warning.

## Exploratory decisions

```json
{
  "E1_CONTRACT_INFORMATION_VALUE_SUPPORTED": false,
  "E2_TRANSITION_TRACKING_INCREMENTAL_VALUE_SUPPORTED": false,
  "E3_STATIC_CONTRACT_CHECK_SUFFICIENT": true,
  "E4_NO_CLEAR_CONTRACT_AWARE_ADVANTAGE": true
}
```

Replication recommendation: **DO_NOT_SPEND_REPLICATION_BUDGET**.

No confirmatory claim is made from this cohort.
