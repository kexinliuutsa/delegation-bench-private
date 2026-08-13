# Experiment Lineage

## Phase 1 — Synthetic delegation-state exploration

- **Question:** Can trajectory state and capability transitions be represented more informatively than isolated action risk?
- **Data:** Synthetic and fixture-driven trajectories from early experiments.
- **Main result:** Candidate state abstractions and transition metrics were feasible, but synthetic evidence could not establish real-agent behavior.
- **Why the next phase was needed:** Environmental influence and causal source could not be inferred from synthetic action patterns.
- **Evidence level:** Pilot/exploratory.

## Phase 2 — Authority-source causal pilot

- **Question:** Can paired intervention distinguish user-directed actions from environment-associated changes?
- **Data:** Early paired authority-source fixtures and causal-oracle prototypes.
- **Main result:** Paired comparison was more informative than action-only attribution, but source labels required difficult oracle assumptions.
- **Why the next phase was needed:** Real rollouts were necessary, and the paper target shifted away from source classification.
- **Evidence level:** Pilot/motivation.

## Phase 3 — Real Coding environmental influence pilot

- **Question:** Does exposure to environmental information imply behavioral adoption?
- **Data:** Real Coding rollouts from Experiments 48–54.
- **Main result:** Exposure and adoption were empirically separable; adoption was sparse and context dependent.
- **Why the next phase was needed:** Sparse causal labels made detector training unstable and suggested studying observable trajectory variation instead.
- **Evidence level:** Pilot/development.

## Phase 4 — v0 cross-paradigm benchmark and monitor failure

- **Question:** Do normal-transition monitors transfer between Coding and Web?
- **Data:** v0 Coding/Web trajectories in `results/multi_agent_delegation/`.
- **Main result:** Coding→Web and Web→Coding transfer exposed catastrophic false-alarm or non-detection modes for NDTR/CDM.
- **Why the next phase was needed:** These failures motivated representation learning and a cleaner delayed-exposure benchmark.
- **Evidence level:** Pilot/development only.

## Phase 5 — PIDR proof of concept

- **Question:** Can cross-paradigm benign alignment and intervention separation improve representation geometry?
- **Data:** v0 Coding/Web development trajectories.
- **Main result:** PIDR-style objectives reduced some paradigm effects and improved selected diagnostics, but mixed evaluation/training pools required stricter methodology.
- **Why the next phase was needed:** A frozen protocol, clean split, and shared pre-exposure phase were required.
- **Evidence level:** Development/ablation.

## Phase 6 — Benchmark v1 redesign

- **Question:** Can a paired real-agent benchmark isolate delayed intervention while measuring natural pre-exposure variation?
- **Data:** 160 Coding/Web pairs, 320 real GPT-5 trajectories.
- **Main result:** Strict generation isolation, delayed exposure, reconstructed actual exposure, and a preregistered split were implemented; GUI was excluded and the future transfer domain left unassigned.
- **Why the next phase was needed:** The benchmark effect needed confirmatory estimation before model evaluation.
- **Evidence level:** Confirmatory protocol and collection.

## Phase 7 — Benchmark v1 confirmatory measurement

- **Question:** Does divergence increase after exposure, and does the effect survive benign pre-divergence?
- **Data:** 133 exposure-reached v1 pairs.
- **Main result:** Action delta 0.4986 [0.4400, 0.5565]; substantial pre-divergence (45.11%); positive effects in pre-identical and pre-diverged strata.
- **Why the next phase was needed:** The benchmark signal justified a representation-learning evaluation.
- **Evidence level:** Confirmatory.

## Phase 8 — PIDR-v1 development and sealed evaluation

- **Question:** Can PIDR-v1 preserve post-exposure separation while reducing paradigm information?
- **Data:** TRAIN seeds 0–2, DEV seed 3, one-shot seed-4 model-selection-sealed test.
- **Main result:** Sealed post-separation difference 0.3900 [0.2851, 0.5020] and lower paradigm-probe accuracy; absolute pre-benign distance did not improve and downstream-monitor gains were inconclusive.
- **Why another phase may be needed:** External paradigms, model families, and a new sealed test are required for PIDR-v2 or stronger monitoring claims.
- **Evidence level:** Development plus one-shot model-selection-sealed evaluation.

## Phase 9 — Cross-model replication line (archived)

**Lineage:** 81 → 81.1 → 81.3 → 81.4 → 81.5 → 81.6 → 81.7 → 81.7b → 81.8 → 81.9 → 81.10 → 81.10R → 81.10Q → **ARCHIVED**.

The v1.3 protocol and scientific smoke qualified successfully, but the fresh-sealed gpt-4.1 cohort was truncated by provider quota exhaustion. The incomplete paired subset eliminated one task family, so neither the primary analysis nor a secondary sealed analysis was authorized. Final status: **CROSSMODEL_REPLICATION_ARCHIVED_RESOURCE_TRUNCATION**; the hypothesis was neither confirmed nor falsified.
