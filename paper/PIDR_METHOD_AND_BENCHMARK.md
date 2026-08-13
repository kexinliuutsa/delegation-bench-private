# Legacy PIDR Method Note

> Paper-facing terminology is frozen on Route A. Use [`PIBR_METHOD_AND_BENCHMARK.md`](./PIBR_METHOD_AND_BENCHMARK.md): **PIBR, Paradigm-Invariant Behavioral Representation**. `PIDR` remains only as a legacy implementation/artifact name so existing models and result paths remain reproducible. The paper does not claim an independently validated delegation or authority ground truth.

This document freezes the paper-facing definition of the current implementation. It deliberately distinguishes the benchmark target, the representation learner, and the downstream monitor. PIDR is a representation learner, not an attack detector.

## 1. Problem and target

At step `t`, an agent transition is

```text
tau_t = (h_t, o_t, a_t),
```

where `h_t` is the observable trajectory prefix, `o_t` is the current tool observation, and `a_t` is the current tool action. A delegation representation is

```text
z_t = f_theta(tau_t).
```

“Paradigm invariant” means invariant to benign changes in the agent interaction paradigm—here, coding tools versus Web interaction tools—while remaining sensitive to paired intervention-induced changes in delegation evolution. It does **not** mean invariant to every action, task, state, or model change.

The benchmark does not establish that an intervention is malicious or that an action is unsafe. Its observable target is **paired intervention-induced behavioral divergence**: a control and treatment share the legitimate user task, seed, model, and non-intervention fixture state; the treatment changes only environmental information. Step-level evaluation marks treatment actions that a monotone alignment classifies as new or modified relative to the paired control. This is a behavioral-divergence proxy, not authority-source ground truth.

## 2. Exact encoder used in the proof of concept

The implementation is intentionally small. For each transition it constructs a 96-dimensional signed-hashed vector from:

- task tokens;
- current action tokens;
- current observation tokens;
- current tool and observation-source tokens;
- a five-bin normalized trajectory-progress summary;
- the current shared capability level;
- the change from the previous capability level.

The shared capability vocabulary is `A0 observe`, `A1 local modify`, `A2 execute`, `A3 persistent change`, and `A4 external side effect`. Thus, the current proof of concept summarizes `h_t` through progress and previous-to-current capability change; it does not contain a Transformer, LSTM, or unrestricted full-history text aggregator. The vector is L2-normalized and projected by a learned linear map from 96 to 24 dimensions. The architectural novelty is not the projection head; the contribution is the supervision objective over paired trajectories.

## 3. Learning objective

For normalized-progress-aligned benign control transitions from paradigms `p` and `q`, PIDR minimizes the squared latent distance:

```text
L_align = mean ||f_theta(tau_i^p) - f_theta(tau_i^q)||_2^2.
```

For aligned control/treatment transitions classified as modified under the paired intervention, it uses a margin-separation loss:

```text
L_sep = mean max(0, m - d(f_theta(tau_i^C), f_theta(tau_i^T)))^2.
```

The total objective is

```text
L_PIDR = L_align + lambda L_sep.
```

The released proof of concept uses margin `m = 0.45`, equal per-example SGD weight (`lambda = 1` at the example level), 160 epochs, a deterministic initialization seed of 63, and a deterministic training shuffle seed of 6301. Because there are 313 alignment examples and 121 separation examples, their aggregate contribution also reflects those empirical counts. Treatment-only `NEW` steps remain part of the evaluation proxy but do not form separation-training pairs because no corresponding control step exists.

The separation term prevents the trivial solution in which all paradigms and interventions collapse to one point. The latent-collapse audit confirms non-zero held-out variance and increased control/treatment separation. The shuffled-task ablation shows that most of the gain comes from distribution-level delegation progression rather than semantic one-to-one task identity; correct task correspondence provides a smaller incremental gain.

## 4. Training and evaluation protocol

| Paradigm | Agent | Task families | Styles | Seeds | Pairs | Trajectories |
|---|---|---:|---:|---:|---:|---:|
| Coding | GPT-5 minimal coding tool agent | 4 | 4 | 3 | 48 | 96 |
| Web | GPT-5 minimal local-Web tool agent | 4 | 4 | 3 | 48 | 96 |
| Total | 2 controlled agent paradigms | 8 | 4 | 3 | 96 | 192 |

Each paradigm contains `4 tasks x 4 intervention styles x 3 seeds x 2 conditions`. Conditions are paired control/treatment rollouts. Coding and Web use the same underlying model but different tool/action spaces. Web submissions affect only isolated simulated session state.

Representation training uses seeds 0 and 1 from both paradigms: 313 benign alignment pairs and 121 divergent control/treatment transition pairs. Seed 2 is held out for representation evaluation. The original Experiment 66 evaluation pool contained all 48 Web pairs: 32 seed-0/1 pairs used by PIDR's alignment/separation training and 16 fully held-out seed-2 pairs. Those 32 pairs were not stored in the downstream 5NN normal memory and their labels were not used by the monitor, but they did provide representation-level domain-adaptation supervision. Consequently, the original 48-pair false-alarm collapse must be read as a mixed seen/unseen diagnostic, not held-out generalization. The primary seed-2 analysis finds 15/16 raw false alarms versus 0/16 with PIDR; the Wilson 95% intervals are `[0.7167, 0.9889]` and `[0, 0.1936]`. Step-AUROC bootstrap intervals overlap. The report therefore supports a held-out false-alarm distribution shift but not a precise population error rate or resolved AUROC improvement. This still evaluates a paradigm observed during PIDR training; it is not a claim of generalization to a completely unseen third paradigm.

## 5. Downstream monitoring

PIDR outputs delegation states. The downstream monitor is replaceable. The frozen evaluation uses the same unsupervised 5-nearest-neighbor transition-distance rule for raw and PIDR inputs:

```text
Delta z_t = z_t - z_{t-1}
score_t = mean distance to the five closest normal Coding transitions.
```

Thresholds are computed using leave-one-Coding-control-out calibration. No unsafe, authority-source, or divergence label is read by the detector. PIDR improves the representation presented to this fixed monitor; it is not itself the decision rule.

## 6. Benchmark terminology

Use these terms consistently:

- **Control trajectory:** execution in the matched environment without the intervention content.
- **Treatment trajectory:** execution with the environmental-information intervention.
- **Exposure:** intervention content appears in the observation history.
- **Operational adoption:** a later action has an explicit observable correspondence with the intervention content.
- **Behavioral divergence proxy:** a treatment action is new or modified under monotone control/treatment alignment.
- **Capability expansion:** the treatment reaches a higher shared capability tier than its control.

Do not substitute “attack success,” “malicious action,” “unsafe behavior,” or “causal authority label” unless an independent annotation supports that stronger claim.

## 7. Baseline taxonomy and intellectual context

The evaluated alternatives correspond to established monitoring ideas rather than a collection of paper-specific acronyms:

- **Action-frequency anomaly:** rarity of the current action signature.
- **Sequence reconstruction:** reconstruction error under a normal-only trajectory autoencoder.
- **Markov transition model:** negative log-likelihood of the next action signature given the previous signature.
- **Retrieval-based transition anomaly (NDTR):** distance to normal trajectory transitions.
- **Counterfactual continuation monitor (CDM):** deviation from a matched or retrieved normal continuation.
- **Paired alignment oracle (CAAO):** post-hoc control/treatment alignment with exposure information; this has stronger information access and is not a deployable baseline.

PIDR is related to domain-invariant representation learning, but differs from domain-adversarial training and invariant risk minimization because its objective explicitly preserves paired intervention deviations rather than only removing domain information. It is also related to one-class anomaly representation learning and to process-mining conformance alignment, while targeting agent delegation evolution rather than generic sample normality or compliance with a prescriptive process model.

Primary references:

- Ganin et al., [Domain-Adversarial Training of Neural Networks](https://www.jmlr.org/papers/v17/15-239.html), JMLR 2016.
- Arjovsky et al., [Invariant Risk Minimization](https://arxiv.org/abs/1907.02893), 2019.
- Ruff et al., [Deep One-Class Classification](https://proceedings.mlr.press/v80/ruff18a.html), ICML 2018.
- de Leoni, Lanciano, and Marrella, [Aligning Partially-Ordered Process-Execution Traces and Models Using Automated Planning](https://ojs.aaai.org/index.php/ICAPS/article/view/13911), ICAPS 2018.

## 8. Reproduction map

- Encoder and objective: `models/paradigm_invariant_delegation.py`
- PIDR training/evaluation: `experiments/paradigm_invariant_delegation_representation.py`
- Alignment-loss ablation: `experiments/pidr_alignment_ablation.py`
- Matched-vs-shuffled control and collapse audit: `experiments/pidr_shuffled_alignment_control.py`
- Frozen downstream monitor: `experiments/pidr_downstream_monitor.py`
- Five-shot threshold calibration: `experiments/pidr_adaptive_threshold_calibration.py`
- Confidence intervals: `experiments/pidr_statistical_report.py`
- Universal rollout schema: `benchmarks/multi_agent/schema.json`

## 9. Current claim boundary

The supported claim is that normal-transition monitors confuse paradigm shift with deviation, and that a paired alignment-plus-separation representation changes this failure mode under a fixed downstream monitor. Held-out claims must use the seed-2-only statistical report; the original 48-Web-pair result is transductive/mixed because PIDR used seed-0/1 Web pairs during representation training. The current evidence does not establish maliciousness, universal authority attribution, generalization to an unseen third paradigm, or a production-ready zero-error monitor.
