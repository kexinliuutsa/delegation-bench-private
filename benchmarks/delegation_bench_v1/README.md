# Multi-Paradigm Delegation Evolution Benchmark v1

Benchmark v1 is a new, reproducible real-agent collection protocol. Existing
Experiment 48–67 Coding/Web trajectories are v0 pilot/development data and are
not copied, relabeled, or reinterpreted as v1.

## Design

The core collection contains 160 strict pairs and 320 real trajectories: two
paradigms (Coding and Web), four benign task families per paradigm, four bounded
intervention styles, five seeds, and two conditions.

A third execution paradigm is intentionally left unassigned in the core protocol.
It will only be instantiated if a mature and independently validated real-agent
environment is available. Mock GUI trajectories are not used as evidence of
cross-paradigm generalization. The existing GUI adapter is marked
`EXPERIMENTAL_UNUSED_ADAPTER` and contributes no benchmark data or results.

Unlike v0, where exposure generally occurred at the beginning, v1 schedules a
shared intervention-free environment prefix. Steps before the deterministic
boundary `k ∈ {3,4,5}` use the same initial workspace and generation settings.
At the boundary, the runner makes either a matched benign control observation or
the declared treatment observation available. `actual_exposure_step` is derived
from what the real agent observed; it is never copied from the schedule. An agent
that finishes first is recorded as `EARLY_TERMINATION`.

Condition, intervention style, and pair identifiers are never inserted into the
agent task or system prompt. Session schedules remain runner-private. External
effects are confined to isolated mock/session state. No synthetic trajectories
are permitted.

## Capability abstraction

Primitive actions remain available in every trajectory. They are additionally
mapped to `A0_OBSERVE`, `A1_LOCAL_MODIFY`, `A2_EXECUTE`,
`A3_PERSISTENT_CHANGE`, or `A4_EXTERNAL_SIDE_EFFECT`. A tier is an operational
capability description, not a safety judgment.

## Pre-registered split

- Training: Coding + Web seeds 0, 1, 2
- Development: Coding + Web seed 3
- In-domain sealed test: Coding + Web seed 4
- Future out-of-domain test: `UNASSIGNED`, `DATA_NOT_COLLECTED`

Seed 4 cannot be used for PIDR fitting, threshold calibration, aggregation or
hyperparameter selection, or intervention-label-based tuning. A future third
paradigm is an additional external test and never replaces this sealed test.

## Claim boundary

When generation isolation and observed exposure audits pass, v1 supports:

- randomized paired trajectory-level intervention-effect estimates;
- post-exposure divergence timing when exposure is actually observed.

It does not automatically support unsafe-action claims, malicious-intent claims,
human-authorization violations, or causal claims about internal reasoning.

The benchmark contains no authority, unsafe, attack-success, drift, source, or
oracle labels and never records private reasoning or hidden chain-of-thought.

## Collection

Materialize and audit without running agents:

```bash
python3 experiments/build_delegation_bench_v1.py
python3 experiments/run_delegation_bench_v1.py
```

Phase 1 real collection requires credentials and explicitly passes `--execute`:

```bash
python3 experiments/run_delegation_bench_v1.py \
  --paradigm coding --execute --resume --model MODEL --max-workers 4
python3 experiments/run_delegation_bench_v1.py \
  --paradigm web --execute --resume --model MODEL --max-workers 4
```

Web collection is intentionally not started automatically after Coding. It is
gated by the Coding validity decision. The unused GUI adapter is not a collection
target for core v1.
