# Table Plan

## Table 1 — Benchmark composition and protocol

Contents: paradigms, tasks, styles, seeds, pair counts, exposure steps, exposure reach. Sources:

- `benchmarks/delegation_bench_v1/collection_manifest.json`
- `results/delegation_bench_v1/status.json`
- `results/delegation_bench_v1/pidr_v1_sealed_test/sealed_test_counts.json`

## Table 2 — Confirmatory pre/post divergence

Contents: All/Coding/Web pre, post, delta, CI, interaction, capability delta. Sources:

- `results/delegation_bench_v1/confirmatory/paradigm_summary.csv`
- `results/delegation_bench_v1/confirmatory/bootstrap_summary.json`
- `results/delegation_bench_v1/confirmatory/benchmark_findings_frozen.json`

## Table 3 — Pre-diverged vs pre-identical

Contents: N, action delta CI, capability delta CI, positive proportion. Source:

- `results/delegation_bench_v1/pre_exposure_variation/prediverged_vs_identical.csv`

## Table 4 — Pilot cross-paradigm baseline failure

Contents: direction, method, AUROC, benign FA, pair detection; labeled pilot/development. Sources:

- `results/multi_agent_delegation/cross_domain_transfer/coding_to_web_transfer.csv`
- `results/multi_agent_delegation/bidirectional_transfer/web_to_coding.csv`

## Table 5 — PIDR-v1 development

Contents: representation geometry, monitor diagnostics, paradigm probe, ablations. Sources:

- `results/delegation_bench_v1/pidr_v1/dev_representation_metrics.csv`
- `results/delegation_bench_v1/pidr_v1/dev_monitor_metrics.csv`
- `results/delegation_bench_v1/pidr_v1/paradigm_probe.csv`
- `results/delegation_bench_v1/pidr_v1/ablation_results.csv`

## Table 6 — PIDR-v1 sealed test

Contents: geometry, bootstrap differences, probe, monitor metrics, H1–H4. Sources:

- `results/delegation_bench_v1/pidr_v1_sealed_test/representation_geometry.csv`
- `results/delegation_bench_v1/pidr_v1_sealed_test/bootstrap_comparisons.csv`
- `results/delegation_bench_v1/pidr_v1_sealed_test/downstream_monitor.csv`
- `results/delegation_bench_v1/pidr_v1_sealed_test/hypothesis_results.json`

## Table 7 — Retrospective published representation baselines

Sources: `representation_development_results.csv`, `representation_existing_evaluation_results.csv`, and `representation_bootstrap_comparisons.csv` under `results/delegation_bench_v1/published_baselines/`.

## Table 8 — Sequence baselines and shortcut diagnostics

Sources: `sequence_development_results.csv`, `sequence_existing_evaluation_results.csv`, and `deeplog_shortcut_results.csv` under `results/delegation_bench_v1/published_baselines/`.
