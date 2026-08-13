# DelegationBench v1 Confirmatory PRE/POST Measurement

## Confirmatory analyses

The pair is the statistical unit. Of 160 complete pairs, 133 had reconstructed actual exposure and met all preregistered inclusion rules; 27 exposure-before-termination pairs were not assigned fabricated POST windows.

| Paradigm | N | Pre action div | Post action div | Delta | 95% CI | P(Delta>0) |
|---|---:|---:|---:|---:|---:|---:|
| All | 133 | 0.2199 | 0.7186 | 0.4986 | [0.4400, 0.5565] | 0.895 |
| Coding | 80 | 0.2448 | 0.5729 | 0.3281 | [0.2607, 0.3921] | 0.838 |
| Web | 53 | 0.1824 | 0.9385 | 0.7561 | [0.6875, 0.8192] | 0.981 |

| Paradigm | N | Pre capability div | Post capability div | Delta | 95% CI |
|---|---:|---:|---:|---:|---:|
| All | 133 | 0.0451 | 0.3608 | 0.3157 | [0.2716, 0.3623] |
| Coding | 80 | 0.0281 | 0.2021 | 0.1740 | [0.1423, 0.2061] |
| Web | 53 | 0.0708 | 0.6005 | 0.5297 | [0.4570, 0.6018] |

| Metric | Coding | Web | Interaction difference | 95% CI |
|---|---:|---:|---:|---:|
| Action delta | 0.3281 | 0.7561 | 0.4281 | [0.3322, 0.5196] |
| Capability delta | 0.1740 | 0.5297 | 0.3557 | [0.2766, 0.4329] |

Post-exposure trajectory divergence is higher than pre-exposure divergence under the randomized paired intervention protocol. This is intervention-associated behavioral/capability divergence, not an unsafe-behavior or authorization label.

## Exploratory analyses

Task-family, intervention-style, exposure-step, trajectory-length, and recovered-pair sensitivity results are explicitly exploratory and are reported in their corresponding CSV files. Trajectory length is a post-treatment variable, not a confounder.

## Freeze and leakage audit

Protocol hashes matched; split and statistical plan were unchanged; all 320 raw trajectory hashes and PIDR model-file hashes remained unchanged; no rollout, label, aggregation selection, threshold tuning, or PIDR operation occurred. Seed 4 was analyzed only under this preregistered PRE/POST measurement.

Recommendation: **PROCEED_TO_PIDR_V1**.
