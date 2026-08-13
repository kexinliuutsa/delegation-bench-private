# Pre-Exposure Variation Audit

Status: **PRE_VARIATION_CONSISTENT_WITH_BENIGN_STOCHASTICITY**.

All 133 exposure-reached pairs passed generation isolation and intervention-hidden checks. Pre-exposure behavioral divergence occurred in 60/133 pairs (45.11%). Both PRE_IDENTICAL and PRE_DIVERGED strata show positive post-minus-pre action divergence with pair-bootstrap intervals excluding zero: [0.6447, 0.7532] and [0.1773, 0.3287], respectively. Thus intervention-associated variation is observed on top of substantial benign execution-path variation.

No single task, seed, style, or exposure-step stratum contains more than half of all pre-diverged cases. Scheduled step 5 nevertheless has an elevated within-stratum divergence rate (78.38%) and should remain a reported structural sensitivity, not a filtered subgroup. Collection-order and temporal-distance metadata were reconstructed from timestamps; worker identity was not recorded and remains UNKNOWN. The pseudo-pair comparison is exploratory and is not a causal control.

PIDR-v1 remains frozen and its model-selection-sealed seed-4 evaluation was not opened. Recommendation: **PROCEED_TO_PIDR_V1_MODEL_SELECTION_SEALED_TEST**.
