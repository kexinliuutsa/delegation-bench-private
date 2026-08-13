# PIDR-v1 Model-Selection-Sealed Test

This is the single frozen seed-4 evaluation. PIDR-v1 and the 5NN diagnostic monitor were not modified or recalibrated.

| Geometry | Raw | PIDR-v1 |
|---|---:|---:|
| Pre-benign distance | 0.9156 | 0.9349 |
| Post separation | 0.2979 | 0.6411 |
| Separation/alignment ratio | 0.3254 | 0.6857 |

| Frozen monitor | Raw | PIDR-v1 |
|---|---:|---:|
| AUROC | 0.8154 | 0.8584 |
| Benign FA | 0.0000 | 0.0312 |
| Pair detection | 0.4062 | 0.3438 |

Hypotheses: {"H1": "SUPPORTED", "H2": "INCONCLUSIVE", "H3": "SUPPORTED", "H4": "INCONCLUSIVE"}. PIDR-v1 does not achieve lower absolute pre-benign distance if the table does not show it; no benign-alignment claim is made in that case. No third-paradigm or safety/authority claim is supported.

## Statistical amendment

The ratio-difference pair bootstrap was corrected to compute aggregate mean(post)/mean(pre) within each replicate. Its CI crosses zero, so H2 is INCONCLUSIVE. No model, threshold, sample, or point estimate was changed.
