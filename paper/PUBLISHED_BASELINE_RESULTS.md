# Published Baseline Results

Experiment 75 is a **retrospective published-baseline comparison** on the previously opened seed-4 evaluation set.

Generic alignment reduced absolute pre-benign distance but did not preserve intervention-associated post separation: CORAL reached 0.2812 and MMD 0.3157, versus 0.6411 for frozen PIDR-v1. PIDR-minus-CORAL post-separation difference was 0.3599; PIDR-minus-MMD was 0.3254. Pair-bootstrap intervals are reported in the results table. Downstream monitor AUROC improvements remained uncertain: PIDR-minus-CORAL 0.0508, 95% CI [-0.0557, 0.1582], and PIDR-minus-MMD 0.0555 [-0.0498, 0.1699].

This supports a selective representation-separation story, not a confirmed detector improvement. DeepLog-style AUROC was 0.5527 with 28.13% benign false alarm and did not provide incremental sequence-baseline value. Seed 4 is not described as sealed, untouched, or confirmatory here.
