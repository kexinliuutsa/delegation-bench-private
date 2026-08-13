# Paper Draft v0.1

## Provisional titles

1. *Learning Paradigm-Invariant Delegation Representations for Cross-Agent Monitoring*
2. *Beyond Agent-Specific Normality: Measuring and Representing Delegation Evolution Across Agent Paradigms*
3. *DelegationBench: Measuring Cross-Paradigm Agent Behavior Under Delayed Environmental Intervention*

These titles are provisional; no final title is selected.

## Abstract

Trajectory-level monitors for long-horizon agents may encode agent-specific execution style rather than behavior that transfers across execution paradigms. We study this problem with DelegationBench v1, a paired benchmark spanning Coding and Web agents. The benchmark contains 160 control/treatment pairs and 320 real GPT-5 trajectories, with environmental interventions delayed until steps 3, 4, or 5 under strict generation isolation and a shared pre-exposure protocol. Among 133 pairs that reached exposure, action-sequence divergence increased after exposure by 0.4986 on average (95% pair-bootstrap CI [0.4400, 0.5565]); the response magnitude differed between Coding and Web. This effect occurs against substantial benign variation: 45.11% of exposure-reached pairs had already diverged behaviorally before exposure. We further introduce PIDR-v1, a lightweight representation learner that combines pre-exposure cross-paradigm invariance, post-exposure matched separation, temporal consistency, and variance preservation. In a one-shot model-selection-sealed seed-4 evaluation, PIDR-v1 produced stronger post-exposure representation separation than the raw encoder and reduced paradigm-probe accuracy. However, it did not reduce absolute pre-exposure benign distance, and improvements under a frozen downstream 5NN monitor were statistically inconclusive. These results support representation-level progress in preserving intervention-associated variation while suppressing some paradigm information, but they do not establish universal paradigm invariance or a reliable detector. Robust downstream monitoring under benign path variation remains open.

## 1. Introduction

Long-horizon agents increasingly operate through structured sequences of observations and state-changing actions. A coding agent may inspect a repository, edit a file, execute tests, and update configuration. A web agent may navigate pages, inspect content, populate a form, and commit an action in an isolated session. GUI-like agents introduce yet another interface and action vocabulary. Across these settings, the safety-relevant object is not always an isolated action. The meaning of an action can depend on the task, the preceding observations, the capability state reached so far, and how information encountered during execution affects subsequent behavior.

Existing approaches to agent monitoring commonly emphasize three related abstractions: action-level risk classification, trajectory anomaly detection, and learning a distribution of normal execution behavior [CITATION NEEDED]. These approaches are useful, but each can conflate behavioral novelty with a meaningful change in how an agent uses its delegated capabilities. An action classifier sees the current operation but may miss how it arose. A sequence model can detect an unusual path without explaining whether the path is inappropriate for the task. A learned normality model depends on the execution distribution used to define “normal.”

This last dependence becomes acute across agent paradigms. Coding and Web agents can use the same underlying language model while exposing different tools, observations, and benign control flows. Reading a file, opening a page, running a test, and submitting an isolated form have different surface forms and frequencies. A monitor trained on Coding trajectories may therefore flag normal Web behavior merely because Web execution lies outside its learned support. Conversely, a representation that indiscriminately collapses cross-paradigm differences may also erase the intervention-associated variation that monitoring is intended to preserve.

Consequently, rare or unseen trajectories are not equivalent to delegation violations. Novelty can reflect an unfamiliar task, a stochastic but benign path, a new tool vocabulary, or a genuine response to environmental information. Operational trajectory divergence likewise does not establish unsafe behavior or a violation of human authorization. A benchmark must separate the intervention from the pre-existing execution path before it can measure whether behavior changes after environmental information becomes observable.

DelegationBench v1 addresses this measurement problem through delayed paired intervention. Each experimental unit contains a control and treatment trajectory with the same task, seed, model, runner, system prompt, tool schema, initial state, and non-intervention artifacts. The intervention is unavailable before a deterministically scheduled boundary at step 3, 4, or 5. At the boundary, only a declared environmental observation differs. The actual exposure step is reconstructed from the observed trajectory rather than assumed from the schedule. This design creates a shared pre-exposure phase in which benign stochastic path variation can be measured separately from post-exposure change.

The benchmark contains 160 pairs and 320 real GPT-5 trajectories across Coding and Web. Of these, 133 pairs reached exposure and supported pre/post analysis; 27 Web treatment trajectories terminated before exposure and remain in the benchmark without fabricated post-exposure outcomes. In the exposure-reached cohort, mean action divergence increased from 0.2199 before exposure to 0.7186 after exposure. The mean increase was 0.4986 (95% CI [0.4400, 0.5565]). Coding and Web exhibited different response magnitudes: their mean increases were 0.3281 and 0.7561, respectively, with a Web-minus-Coding interaction of 0.4281 (95% CI [0.3322, 0.5196]).

The shared prefix also reveals why ordinary anomaly framing is difficult. Sixty of 133 exposure-reached pairs—45.11%—had already diverged behaviorally before exposure. This variation was not invalid generation: all pairs passed generation-isolation checks and the intervention remained hidden. Both naturally pre-identical and naturally pre-diverged strata nevertheless showed positive post-minus-pre action divergence with confidence intervals excluding zero. Thus, intervention-associated variation is observed on top of substantial benign execution-path variation, rather than only in trajectories that were identical beforehand.

Motivated by earlier pilot failures of cross-paradigm anomaly monitors, we introduce Paradigm-Invariant Delegation Representation v1 (PIDR-v1). PIDR-v1 is a representation learner, not a detector. It uses deterministic signed hashed text/action features, structured progress and capability features, a learned linear diagonal projection, and L2 normalization. Its objective aligns compatible pre-exposure transitions across paradigms, preserves matched post-exposure control/treatment separation, smooths locally stable temporal transitions, and prevents latent collapse. Condition metadata is used only by the sampler to construct matched pairs and never enters the encoder.

The one-shot model-selection-sealed seed-4 evaluation gives a mixed but informative result. PIDR-v1 increased post-exposure separation from 0.2979 to 0.6411; the paired difference was 0.3900 (95% CI [0.2851, 0.5020]). Paradigm-probe accuracy fell from 0.9959 to 0.8975, indicating that some paradigm-specific information was suppressed. However, pre-benign distance increased from 0.9156 to 0.9349, so the test does not support an absolute benign-alignment claim. Under the same frozen 5NN monitor, AUROC increased modestly, but false alarms increased and pair detection decreased; all associated difference intervals were inconclusive.

This paper makes four contributions:

1. **C1—Benchmark design.** We define DelegationBench v1, a strictly isolated paired Coding/Web benchmark with delayed environmental exposure and reconstructed temporal boundaries.
2. **C2—Empirical finding.** We show a confirmatory post-exposure increase in trajectory and capability-sequence divergence, heterogeneous across paradigms, while documenting substantial benign pre-exposure path variation.
3. **C3—Baseline and generalization analysis.** Pilot/development experiments organize anomaly-monitor families and demonstrate severe cross-paradigm failure modes that motivate representation learning; these results are not treated as v1 confirmatory evidence.
4. **C4—Representation-learning result.** We propose PIDR-v1 and show on a one-shot model-selection-sealed evaluation that it preserves stronger post-exposure separation and reduces paradigm-probe accuracy, while downstream monitoring gains remain unresolved.

### Research Questions

- **RQ1:** Does delayed environmental intervention produce measurable post-exposure trajectory divergence relative to the shared pre-exposure phase?
- **RQ2:** How much benign execution-path variation exists before intervention, and does the post-exposure effect persist on top of that variation?
- **RQ3:** Does intervention-associated response magnitude differ between Coding and Web agent paradigms?
- **RQ4:** Can conventional trajectory-monitoring approaches generalize across paradigms?
- **RQ5:** Can PIDR-v1 learn representations that preserve post-exposure intervention-associated variation while reducing paradigm-specific information?

## 2. DelegationBench v1

DelegationBench v1 has two core paradigms, Coding and Web. A future transfer domain is intentionally **UNASSIGNED** and is not part of the current result. Each paradigm contains four benign task families, four preregistered intervention styles (explicit, indirect, authority impersonation, and multi-step), and five seeds. The resulting benchmark has 80 control/treatment pairs per paradigm, 160 pairs total, and 320 real trajectories.

For each pair, scheduled exposure is deterministically assigned to step 3, 4, or 5. Before that boundary, control and treatment generation is identical in task, seed, model and sampling configuration, runner, system prompt, tool schema, initial environment, permissions, and non-intervention artifacts. At or after the boundary, treatment receives the declared environmental observation through the ordinary tool-observation channel; control receives its matched benign observation. `scheduled_exposure_step` describes the protocol schedule, whereas `actual_exposure_step` is reconstructed from what the agent observed. If the agent terminates first, the outcome is early termination and no post-exposure effect is fabricated.

All 160 pairs passed generation isolation. The complete dataset contains all 320 trajectories, but temporal validity is narrower: 27 Web treatment trajectories terminated before exposure. They are retained for benchmark completeness and pre-prefix uses where allowed, but excluded from the confirmatory PRE/POST analysis. This leaves 133 exposure-reached pairs: all 80 Coding pairs and 53 Web pairs.

## 3. Threat Model

The environment may present agent-observable information through normal interaction channels. In Coding, these channels include repository content, test output, and configuration artifacts. In Web, they include page content, forms, and page-level instructions. The model weights are not compromised; the system prompt is unchanged; tools follow the isolated benchmark environment; and no hidden condition or intervention label is exposed to the agent.

The measurement concern is that environmental information may alter downstream execution behavior. Treatment does not imply maliciousness, unsafe behavior, or an authorization violation. Out of scope are determining malicious intent, proving human authorization violations, reading internal chain-of-thought, measuring real-world external harm, and universal prompt-injection detection.

## 4. Confirmatory Benchmark Results

The full benchmark contains 160 pairs and 320 trajectories. The confirmatory cohort contains 133 exposure-reached pairs: 80 Coding and 53 Web. Mean action divergence was 0.2199 before exposure and 0.7186 after exposure. The mean delta was 0.4986 (95% CI [0.4400, 0.5565]). Coding delta was 0.3281 (95% CI [0.2607, 0.3921]); Web delta was 0.7561 (95% CI [0.6875, 0.8192]). The Web-minus-Coding interaction was 0.4281 (95% CI [0.3322, 0.5196]). Capability-sequence divergence increased by 0.3157 (95% CI [0.2716, 0.3623]).

**Post-exposure trajectory divergence is higher than pre-exposure divergence under the randomized paired intervention protocol.** This is an intervention-associated behavioral measurement, not attack success or an authority violation.

### Benign Path Variation Before Exposure

Among 133 exposure-reached pairs, 60 were already behaviorally divergent before exposure, a rate of 45.11%. The highest within-stratum rates were 60.00% for `configuration_repair`, 58.33% for seed 4, and 78.38% for scheduled step 5. Nevertheless, no task, seed, style, or exposure-step stratum contained more than half of all pre-diverged cases.

For 73 pre-identical pairs, mean post-minus-pre action divergence was 0.6999 (95% CI [0.6447, 0.7532]). For 60 pre-diverged pairs, it was 0.2538 (95% CI [0.1773, 0.3287]). **Intervention-associated variation is observed on top of substantial benign execution-path variation.** An exploratory pseudo-pair comparison found actual PRE control/treatment divergence of 0.2199 and within-condition pseudo-pair divergence of 0.1827. These pseudo-pairs are not causal controls.

## 5. Baseline Taxonomy and Pilot Generalization Evidence

We organize earlier baseline implementations by principle rather than presenting all as novel or published methods:

1. **Action rarity/frequency:** current action frequency; limited by missing task/history context. Literature-inspired; [RELATED-WORK MAPPING REQUIRED].
2. **Sequence reconstruction:** trajectory reconstruction error; novelty can reflect benign paradigm shift. Literature-inspired; [RELATED-WORK MAPPING REQUIRED].
3. **Markov transition anomaly:** likelihood of local action transitions; limited for long-range context and unseen normal paths. Literature-inspired; [RELATED-WORK MAPPING REQUIRED].
4. **NDTR:** retrieves nearest normal transition; project-specific implementation of retrieval-based anomaly monitoring, sensitive to paradigm-specific action support. [RELATED-WORK MAPPING REQUIRED].
5. **C-NDTR:** conditions retrieval on task/phase context; project-specific, but small support still limits generalization. [RELATED-WORK MAPPING REQUIRED].
6. **CDM:** compares counterfactual/matched control continuations; project-specific, with a failure mode of suppressing both false alarms and detections. [RELATED-WORK MAPPING REQUIRED].

### Cross-Paradigm Failure (Pilot / Development Evidence)

In v0 Coding→Web transfer, NDTR achieved AUROC 0.4416 with 100% benign false alarms; CDM achieved AUROC 0.4095 with 0% false alarms and 0% pair detection. In the Web→Coding common-support subset, NDTR achieved AUROC 0.6308 with 100% benign false alarms, while CDM achieved AUROC 0.3141 with 100% benign false alarms. These results are pilot/development evidence only. They motivate learning a representation less tied to surface execution normality; they are not mixed into the v1 confirmatory analysis.

## 6. PIDR-v1 Method

PIDR-v1 represents an observable prefix transition containing task, prior action/tool/observation/capability history, current observation and source, current action and tool, current universal capability state, and normalized progress. The implementation uses signed SHA256-hashed unigrams and bigrams plus structured categorical/scalar features. A learned linear diagonal projection maps these features into a 128-dimensional latent vector, which is L2-normalized. There is no Transformer, MLP, external embedding API, or jointly trained detector.

The objective is

`L = L_pre_invariance + lambda_sep * L_post_sensitivity + beta_temp * L_temporal_consistency + gamma_var * L_variance`.

`L_pre_invariance` aligns audited prefixes strictly before exposure across Coding and Web using compatible progress bins and capability states. `L_post_sensitivity` applies a margin loss to monotonically aligned post-exposure control/treatment transitions. `L_temporal_consistency` smooths adjacent within-trajectory prefixes when capability is unchanged and no exposure boundary is crossed. `L_variance` prevents collapse using target standard deviation 0.05. Selected hyperparameters were latent dimension 128, `lambda_sep=1.0`, `beta_temp=0.1`, margin 0.2, and `gamma_var=0.1`.

Training used seeds 0/1/2; development used seed 3; seed 4 was the one-shot model-selection-sealed evaluation. Pair condition is used only by the sampler to construct matched control/treatment examples. It is never an encoder feature, nor are intervention style, pair identifier semantics, exposure schedule, future outcomes, labels, or private reasoning.

## 7. PIDR-v1 Development Results

Development used 96 TRAIN pairs and 32 DEV pairs. Thirteen early-termination pairs contributed audited pre-prefixes, 83 TRAIN pairs contributed post-exposure samples, and 24 configurations were evaluated. Raw pre-benign distance was 0.9206 versus 0.9562 for PIDR-v1: absolute pre-benign distance did not improve. Post separation increased from 0.3150 to 0.6595, and the separation/alignment ratio increased from 0.3422 to 0.6897. Diagnostic AUROC changed from 0.9053 to 0.9492, benign false alarm remained 0%, and pair detection changed from 50.00% to 53.13%. Paradigm-probe accuracy fell from 1.0000 to 0.8272. These development results informed the frozen selection but do not establish benign alignment.

## 8. Model-Selection-Sealed Evaluation

The one-shot seed-4 test contained 32 pairs (16 Coding, 16 Web); 24 reached exposure and eight terminated first. Raw and PIDR pre-benign distances were 0.9156 and 0.9349. Raw and PIDR post separation were 0.2979 and 0.6411. The post-separation difference was 0.3900 (95% CI [0.2851, 0.5020]). The ratio increased from 0.3254 to 0.6857, but its difference CI was [-0.1869, 4.9602], making H2 inconclusive. Paradigm-probe accuracy fell from 0.9959 to 0.8975.

Under the frozen 5NN monitor, AUROC changed from 0.8154 to 0.8584; delta 0.0431 (95% CI [-0.0635, 0.1533]). Benign false alarms changed from 0% to 3.13%, and pair detection from 40.63% to 34.38%; detection difference CI [-0.2188, 0.0938]. H1 was supported, H2 inconclusive, H3 supported, and H4 inconclusive.

**PIDR-v1 preserves stronger post-exposure intervention-associated separation and reduces paradigm-specific information on the model-selection-sealed test.** This representation improvement did not translate into statistically confirmed downstream monitoring gains.

## 9. Limitations and Discussion

The benchmark covers only Coding and Web using one underlying model. Operational divergence is not safety or authorization ground truth. Exposure non-reach, benign stochastic variation, the lack of absolute alignment improvement, and inconclusive downstream results constrain the claims. A third real paradigm and new model families remain external validation. Seed 4 is now opened and cannot serve as a sealed evaluation for PIDR-v2. Detailed limitations appear in `LIMITATIONS_REGISTER.md`.

## 10. Related Work Placeholder

Trajectory anomaly detection, process monitoring, domain generalization, invariant representation learning, and agent prompt-injection defenses require careful mapping to the baseline taxonomy [CITATION NEEDED]. No priority or “first” claim is made in this draft.

## 11. Conclusion

DelegationBench v1 shows that delayed environmental intervention is associated with increased post-exposure trajectory divergence, while benign paths often diverge even before exposure. PIDR-v1 preserves stronger intervention-associated separation and suppresses some paradigm information, but reliable frozen-monitor improvement remains unresolved. The evidence supports a benchmark and representation-learning contribution, not a solved detector.
