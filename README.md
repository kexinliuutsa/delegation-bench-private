# DelegationBench (Private Research Snapshot)

This private repository preserves the complete research trail for DelegationBench: the core v1 benchmark, published-baseline experiments, the archived delegation-transition line, and the resource-truncated cross-model replication line.

## Start here

- Main project report: [`paper/DelegationBench_Project_Report.md`](paper/DelegationBench_Project_Report.md)
- Claim/evidence registry: [`paper/CLAIM_EVIDENCE_MATRIX.csv`](paper/CLAIM_EVIDENCE_MATRIX.csv)
- Experiment lineage: [`docs/EXPERIMENT_LINEAGE.md`](docs/EXPERIMENT_LINEAGE.md)
- Cross-model final status: [`paper/CROSSMODEL_REPLICATION_FINAL_STATUS.md`](paper/CROSSMODEL_REPLICATION_FINAL_STATUS.md)
- Delegation-transition archive: [`paper/archive/DELEGATION_TRANSITION_FINAL_STATUS.md`](paper/archive/DELEGATION_TRANSITION_FINAL_STATUS.md)

## Repository layout

- `paper/` — project report, evidence matrix, paper-facing interpretations, limitations, and archives.
- `benchmarks/delegation_bench_v1/` — frozen v1 protocols, fixtures, taxonomies, and analysis plans.
- `benchmarks/delegation_bench_crossmodel_v13/` — v1.3 cross-model protocol and fresh-sealed definitions.
- `experiments/` — experiment and audit scripts. Historical scripts are retained to document the research process.
- `models/` — baseline and representation implementations.
- `runners/` — rollout and instrumentation runners. Credentials are read from environment variables and are not stored here.
- `results/delegation_bench_v1/` — core confirmatory benchmark and retrospective method results.
- `results/delegation_bench_crossmodel_v13/` — smoke, sealed collection, recovery, missingness audit, and final archived status.
- `results/delegation_transition_pilot/` — archived transition-line evidence and infrastructure history.
- `docs/` — navigation and repository audit records.

## Current scientific status

The strongest supported result is benchmark-level: post-exposure trajectory divergence exceeds pre-exposure divergence under the paired delayed-exposure protocol, with substantial benign pre-exposure path variation and Coding/Web heterogeneity. PIDR-v1 is supported as a representation-level proof of concept, not as an established downstream detector improvement.

The cross-model replication is archived as incomplete because provider quota exhaustion truncated the gpt-4.1 cohort and removed one task family from complete pairs. No cross-model scientific effect estimate was authorized. The delegation-transition hypothesis was not falsified; that line was archived because incremental transition-state value was not identifiable under the available design and infrastructure.

## Reproducibility and privacy

- This snapshot intentionally retains intermediate protocols, QC reports, failure records, and negative results.
- No API keys, private keys, `.env` files, or credentials are included.
- Model runners expect credentials through environment variables such as `OPENAI_API_KEY`.
- Raw trajectories are included for private reproducibility; do not make the repository public without a new privacy and licensing review.
- Scientific claims should follow `paper/CLAIM_EVIDENCE_MATRIX.csv`, including its allowed and forbidden wording.

## Snapshot scope

This repository is a selected copy of the research workspace. It excludes unrelated project lines and local Git history. See `docs/PRIVATE_SNAPSHOT_MANIFEST.md` and `docs/SENSITIVE_INFORMATION_AUDIT.md`.
