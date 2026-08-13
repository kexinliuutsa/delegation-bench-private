# Experiment 75 — Published Baseline Suite

**RETROSPECTIVE_PUBLISHED_BASELINE_COMPARISON. Seed 4 is a previously opened evaluation set.**

CORAL and MMD use the shared observable-prefix encoder and benign pre-exposure alignment only; PIDR-v1 is frozen and uniquely uses post-exposure paired separation. DeepLog is reported separately. The benchmark confirmatory claims are unchanged.

Representation results are in the CSV tables. Paper positioning: **JOINT_BENCHMARK_REPRESENTATION**. Missing legacy sequence artifact values are explicitly marked rather than invented.

## Implementation caveat

The environment does not provide PyTorch. The sequence implementation is therefore a dependency-light smoothed recurrent-history next-event predictor, not a neural GRU/LSTM reimplementation of DeepLog. It is a DeepLog-style diagnostic only. Q4 remains incomplete for a strict published-implementation comparison, and the paper must not present this row as a faithful DeepLog reproduction. Likewise, CORAL and MMD are dependency-light shared-encoder adaptations; reference-implementation validation remains open.
