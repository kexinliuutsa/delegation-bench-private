# Experiment 78 — Normalizer v2 Report

Normalizer v1 is archived byte-for-byte at `models/action_normalizer_v1_experiment77.py` (SHA256 `03a3b284e0d0a4c7fc7fc80bb5a04b85dd4eb548a3496a6dbf73ef3a594198fa`). Normalizer v2 repairs only deterministic structured runner-field aliases: nested or top-level tool arguments, including `path`, `paths`, `file`, `filename`, `command`, `cmd`, and `arguments`. Missing, unknown, or conflicting schemas abstain. No capability category, contract, support rule, DTM, B0, or B1 logic changed.

The schema-format holdout contains 32 cases: 24 resolvable and 8 expected abstentions. Semantic accuracy, resolvable coverage, and abstention accuracy were each 100%, exceeding the preregistered 95% gates.

Read-only replay of all 80 Experiment 77 trajectories yielded 100% global resolvable coverage, 100% boundary-local coverage, and zero unresolved trajectories. No monitor performance fields were inspected. The Experiment 77 decision file was unchanged.

**Permanent status statement:** Normalizer v2 retrospectively resolves the QC failure, but Experiment 77 is not reclassified as a confirmatory method evaluation. Its decision remains `GROUND_TRUTH_OR_MAPPER_INSUFFICIENT`.

The schema correction is frozen for an independent 20-pair replication. That replication uses new pair IDs, task text, fixture directories and content, and is not executed by Experiment 78.
