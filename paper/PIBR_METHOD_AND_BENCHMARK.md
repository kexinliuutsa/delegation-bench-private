# PIBR: Paradigm-Invariant Behavioral Representation

## Scope

PIBR is a representation learner for anomaly monitoring under agent-paradigm shift. It is not a detector and does not infer delegation, authorization, maliciousness, or unsafe action. Its benchmark target is **paired intervention-induced behavioral divergence**: treatment steps classified as `NEW` or `MODIFIED` relative to a matched control trajectory.

At step `t`, the observable transition is

```text
tau_t = (h_t, o_t, a_t),       z_t = f_theta(tau_t),
```

where `h_t` is observable prefix context, `o_t` is the current observation, and `a_t` is the action. “Paradigm invariant” means that benign Coding/Web behavioral progressions are close enough for a common downstream normal-transition monitor, while paired intervention differences remain distinguishable.

## Released proof-of-concept encoder

The implementation hashes the following into a normalized 96-dimensional vector:

- task, action, observation, tool, and observation-source tokens;
- a five-bin normalized progress indicator;
- a shared coarse capability level (`observe`, `local modify`, `execute`, `persistent change`, `external side effect`);
- previous-to-current capability delta.

The current history summary is progress plus capability transition; it is not a Transformer or unrestricted textual-history encoder. A learned linear `96 -> 24` projection produces `z_t`. The contribution is the training objective, not this projection architecture.

## Objective

For normalized-progress-aligned benign control steps from Coding and Web:

```text
L_align = mean ||f_theta(tau_i^coding) - f_theta(tau_i^web)||_2^2.
```

For aligned `MODIFIED` control/treatment steps:

```text
L_sep = mean max(0, m - d(f_theta(tau_i^C), f_theta(tau_i^T)))^2.
L_PIBR = L_align + lambda L_sep.
```

The implementation uses `m=0.45`, equal per-example weight, 160 epochs, initialization seed 63, and shuffle seed 6301. A fold trained on two seeds contains approximately 313–323 alignment examples and 116–125 separation examples. Treatment-only `NEW` steps remain evaluation targets but do not form separation pairs because they have no control counterpart.

## Data

| Paradigm | Task families | Styles | Seeds | Pairs | Trajectories |
|---|---:|---:|---:|---:|---:|
| Coding | 4 | 4 | 3 | 48 | 96 |
| Web | 4 | 4 | 3 | 48 | 96 |
| Total | 8 | 4 | 3 | 96 | 192 |

All trajectories are real GPT-5 tool-agent rollouts in controlled local environments. The benchmark has one underlying model and two tool paradigms. It is not an unseen-model or unseen-third-paradigm benchmark.

## Three-fold cross-fitting

The primary statistical result is leave-one-seed-out cross-fitting:

```text
Fold 0: train PIBR + Coding memory/calibration on seeds 1/2; test Web seed 0
Fold 1: train PIBR + Coding memory/calibration on seeds 0/2; test Web seed 1
Fold 2: train PIBR + Coding memory/calibration on seeds 0/1; test Web seed 2
```

Every Web pair is evaluated exactly once by a PIBR model that did not observe its seed. Every fold independently retrains PIBR, rebuilds the Coding 5NN transition memory, and recalibrates the 95th-percentile threshold with leave-one-Coding-control-out scores.

| Representation | Pooled OOF AUROC | Pair-cluster 95% CI | Benign FA | Wilson 95% CI | Pair detection |
|---|---:|---:|---:|---:|---:|
| Raw | 0.6564 | [0.6155, 0.7123] | 45/48 | [83.16%, 97.85%] | 45/48 |
| PIBR | 0.6953 | [0.6385, 0.7403] | 0/48 | [0%, 7.41%] | 1/48 |

AUROC intervals overlap, so the paper does not claim a statistically resolved AUROC improvement. The robust result is an **asymmetric operating-point change**: the raw representation fires on nearly all benign Web controls, whereas PIBR is conservative and detects few divergent pairs at the frozen 95th-percentile threshold. This is representation/calibration evidence, not a production-ready detector result.

## Ablations

- Removing benign alignment raises Web false alarms from 0% to 93.75% in the original frozen split.
- Task-family-shuffled alignment retains most gains, indicating that distribution-level progress/capability structure matters more than one-to-one semantic task identity.
- Held-out latent variance remains non-zero and control/treatment distance increases, rejecting trivial representation collapse.
- Five benign target-paradigm controls can trade PIBR's conservative threshold for sensitivity without representation retraining, but calibration variance is large.

## Baseline taxonomy

- action-frequency anomaly;
- sequence reconstruction error;
- Markov next-action surprise;
- retrieval-based transition anomaly (legacy NDTR);
- counterfactual continuation comparison (legacy CDM);
- paired post-hoc alignment oracle (legacy CAAO, stronger information access).

PIBR is related to [domain-adversarial representation learning](https://www.jmlr.org/papers/v17/15-239.html), [invariant risk minimization](https://arxiv.org/abs/1907.02893), [deep one-class classification](https://proceedings.mlr.press/v80/ruff18a.html), and [alignment-based process conformance checking](https://ojs.aaai.org/index.php/ICAPS/article/view/13911). It differs by jointly aligning benign cross-paradigm variation and preserving paired intervention-induced behavioral differences.

## Reproduction

- Legacy implementation: `models/paradigm_invariant_delegation.py`
- PIBR training POC: `experiments/paradigm_invariant_delegation_representation.py`
- Downstream monitor: `experiments/pidr_downstream_monitor.py`
- Three-fold cross-fitting: `experiments/pidr_three_fold_crossfit.py`
- Per-fold results: `results/multi_agent_delegation/pidr_three_fold_crossfit/per_fold_metrics.csv`
- Pooled OOF results: `results/multi_agent_delegation/pidr_three_fold_crossfit/pooled_oof_metrics.csv`

## Claim boundary

Supported: normal-transition anomaly monitors exhibit paradigm-dependent asymmetric failure, and PIBR systematically changes their held-out false-alarm distribution under a fixed downstream rule.

Not supported: delegation or authority ground truth, maliciousness, unsafe-action detection, unseen-paradigm generalization, statistically resolved AUROC superiority, or production-ready sensitivity.

## Threshold and collapse diagnostic

The primary 95th-percentile operating point detects only 1/48 pairs (2.08%,
Wilson 95% CI [0.37%, 10.90%]). We therefore additionally sweep thresholds on
the pooled out-of-fold scores. This sweep is diagnostic: it uses held-out Web
control and divergence labels and must not be interpreted as deployable
threshold selection.

At 0% empirical Web false alarms, PIBR detects 11/48 pairs (22.92%). At 14.58%
false alarms it detects 16/48 (33.33%), and at 18.75% false alarms it detects
18/48 (37.50%). Raw transition kNN detects 2/48, 12/48, and 12/48 at the nearest
corresponding false-alarm ceilings. Thus PIBR has not collapsed to a constant
score: a non-trivial low-false-alarm frontier remains. The frontier is still
weak, however, and does not support describing the downstream monitor as
deployment-ready.

The cross-fitting result establishes generalization to unseen executions within
the Coding/Web paradigm pair used during representation training. It does not
establish zero-shot generalization to a third, previously unseen paradigm.
