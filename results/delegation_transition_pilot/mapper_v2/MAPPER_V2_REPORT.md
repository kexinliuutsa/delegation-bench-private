# ActionCapabilityMapper v2 Report

## Scientific audit

1. Phase 1.1 coverage was low because structured tool arguments were not consistently recovered and common tool actions fell through raw prefix matching.
2. The failure was primarily **parsing/normalization**, not a missing capability taxonomy. No capability IDs were added.
3. The dominant failures were structured `list_files`, `read_file`, `edit_file`, `finish`, and command records with empty/alternate action fields.
4. The remaining opaque proportion is 0.00% globally and 0.00% near candidate regions.
5. No rule originated from DTM/B0/B1 success or failure. The ten diagnostic trajectories were opened only after v2 and its mapper-dev holdout evaluation were frozen.
6. No authorization contract changed.
7. Boundary-local coverage is 100.00%; readiness requires 90%.

## Holdout coverage caveat

The mapper-dev holdout deliberately contains three unknown-binary examples labeled
`unclassified` and three unavailable-script examples labeled `opaque_execution`.
Mapper v2 predicts all six exactly, which is why exact-set accuracy and micro/macro F1
are 1.0. Under the preregistered coverage definition, however, correct abstentions do
not count as covered. Holdout coverage is therefore 42/48 (87.5%), below the 95% hard
gate. The split and examples were not changed after this result was observed.

## Decision

`NOT_READY_MAPPER_V2`
