# Draft Introduction and Contributions — Route A

Agent monitors operate over trajectories whose surface form depends strongly on the interaction paradigm. A coding agent reads files, edits source, and executes tests; a Web agent navigates pages, fills forms, and submits interactions. Even when both are driven by the same underlying model, their action vocabularies, observations, and transition structure differ. A monitor trained to recognize normal behavior in one paradigm may therefore confuse a benign interface shift with anomalous behavior in another.

We study this problem without assuming an authorization or attack ground truth. Our benchmark introduces matched environmental-information interventions into legitimate tasks and records real control/treatment executions. The observable evaluation target is **paired intervention-induced behavioral divergence**: treatment actions that are new or modified relative to their matched controls. It does not establish that an intervention is malicious, an action is unsafe, or an agent exceeded delegated authority.

The benchmark contains controlled Coding and Web agents using the same underlying model. Each paradigm has four task families, four intervention styles, three seeds, and paired conditions, yielding 48 pairs and 96 trajectories per paradigm. Both paradigms reconstruct treatment exposure in 48/48 trajectories with no prompt-condition leakage. Yet their observed responses differ: operational adoption is 12.5% for Coding and 25.0% for Web, and capability expansion appears in 0% and 6.25% of pairs. These differences motivate cross-paradigm monitoring rather than a universal action vocabulary.

Existing normal-transition monitors fail asymmetrically under this shift. Coding-trained raw transition monitoring flags nearly every benign Web trajectory; a conservative counterfactual monitor can avoid alarms only by detecting nothing. Reverse transfer is likewise unusable and additionally exposes task-router coverage failures. The missing abstraction is therefore not merely a stronger anomaly score, but a behavioral representation that suppresses benign paradigm variation while preserving intervention-sensitive differences.

We introduce **PIBR, Paradigm-Invariant Behavioral Representation**. PIBR maps observable trajectory transitions into latent behavioral states. Its objective combines benign cross-paradigm alignment with paired intervention separation: normal Coding/Web progressions are pulled together, while modified control/treatment transitions are kept apart by a margin. PIBR is not a detector. A replaceable downstream monitor operates on PIBR transitions.

We evaluate PIBR with three-fold leave-one-seed-out cross-fitting. Every fold retrains PIBR on two seeds from both paradigms, rebuilds a Coding-only 5NN normal-transition memory, recalibrates its threshold using Coding controls, and evaluates the held-out Web seed. Every one of the 48 Web pairs is scored exactly once by a representation that did not observe its seed. Pooled out-of-fold raw monitoring obtains AUROC 0.6564 (pair-cluster bootstrap 95% CI `[0.6155, 0.7123]`) and flags 45/48 benign controls. PIBR obtains AUROC 0.6953 (`[0.6385, 0.7403]`) and flags 0/48 controls (Wilson 95% CI `[0, 7.41%]`). Because AUROC intervals overlap, we do not claim statistically resolved ranking superiority. Instead, the principal result is a reproducible change in the monitor's asymmetric operating failure: raw features produce catastrophic false alarms, whereas PIBR is overly conservative and detects only 1/48 divergent pairs at the frozen 95th-percentile threshold.

Ablations explain this behavior. Removing benign alignment restores 93.75% Web false alarms, showing that intervention separation alone is insufficient. Shuffling semantic task correspondence retains most of PIBR's benefit, indicating that it primarily aligns distribution-level progression rather than memorizing matched task identity. A collapse audit finds non-zero held-out variance and increased intervention separation. Finally, five benign target-paradigm controls recover monitoring sensitivity without retraining PIBR, although the resulting threshold has substantial small-sample variance.

## Contributions

1. **A paired cross-paradigm behavioral benchmark.** We release 96 matched intervention pairs and 192 real Coding/Web trajectories with a universal schema, integrity audits, operational exposure/adoption measurements, and behavioral-divergence evaluation.

2. **A characterization of asymmetric anomaly-monitor failure.** Normal-transition methods mistake benign paradigm shift for anomaly or avoid false alarms by becoming insensitive. Three-fold cross-fitting shows that this failure is not an artifact of evaluating representation-training executions.

3. **PIBR, a behavioral representation objective.** PIBR aligns benign cross-paradigm progression while preserving paired intervention differences, cleanly separating representation learning from downstream monitoring.

4. **Ablation and uncertainty analysis.** Alignment removal, task shuffling, collapse checks, pair-cluster bootstrap, Wilson intervals, and five-shot calibration establish what the method learns and where current evidence remains limited.

## Claim boundary

This work establishes a controlled two-paradigm behavioral-monitoring result for one underlying model. It does not provide delegation or authorization labels, identify malicious actions, demonstrate an unseen third paradigm, or deliver a production-ready detector. The method's current strength is suppression of cross-paradigm false alarms; sensitivity remains an open downstream-calibration problem.

The out-of-fold threshold sweep rules out the degenerate explanation that PIBR
obtains zero false alarms only by assigning an indistinguishable score to every
trajectory. At an empirically diagnostic 0% Web false-alarm point it detects
11/48 intervention-divergent pairs, rising to 18/48 at 18.75% false alarms.
These thresholds use held-out labels and are not deployable operating points.
They show retained intervention sensitivity, but also confirm that sensitivity
remains limited. Our generalization claim is consequently restricted to unseen
executions within the already observed Coding/Web paradigm pair, rather than an
unseen third paradigm.
