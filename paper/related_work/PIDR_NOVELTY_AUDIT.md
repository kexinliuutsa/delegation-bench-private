# PIDR-v1 Novelty Audit

## Executive assessment

PIDR-v1 should not be positioned as inventing invariant representation learning. Domain alignment, domain-adversarial feature learning, covariance alignment, MMD alignment, invariant prediction, and contrastive domain generalization are established method families. Likewise, using a margin to separate paired examples is standard metric-learning machinery, and paired interventions already appear as weak supervision in causal representation learning.

The potentially novel contribution is narrower and compositional: applying representation learning to **security-monitor transfer across heterogeneous agent execution paradigms**, with a delayed paired protocol that (i) aligns audited pre-exposure progression across Coding and Web and (ii) preserves matched post-exposure intervention-associated differences. Our search found extensive work on agent safety evaluation, indirect prompt injection, runtime policy enforcement, domain invariance, and intervention-aware causal representation. We found limited direct evaluation of a normality-based security monitor transferred between agent paradigms with different action spaces. This is a literature-search finding, not a proof of absence.

## Direct answers

1. **Is “paradigm-invariant representation learning” itself novel?** No. DANN [@ganin2016dann], Deep CORAL [@sun2016deepcoral], DAN/MMD [@long2015dan], IRM [@arjovsky2019irm], and SelfReg [@kim2021selfreg] establish the broader family.
2. **Is benign distribution alignment novel?** No. Distribution and covariance alignment are canonical.
3. **Is margin-based separation of treatment/control pairs novel?** No. Pairwise contrastive and margin objectives are established; weakly supervised and causal representation papers also use paired changes or interventions [@locatello2020weak; @brehmer2022weakcausal].
4. **What combination may be novel?** The problem and evaluation combination: heterogeneous agent-trajectory prefixes, audited delayed intervention pairs, benign progression alignment, preservation of post-exposure paired variation, and downstream security-monitor transfer.
5. **Is PIDR simply DANN/CORAL/MMD/IRM applied to trajectories?** No, but it is closely related. PIDR uses a deterministic hashed trajectory encoder and learned diagonal scaling. It minimizes sampled pre-exposure pair distance and uses a margin to retain post-exposure pair distance. It has no adversarial domain classifier (DANN), no covariance-matching loss (CORAL), no RKHS mean-embedding loss (MMD/DAN), and no shared optimal prediction-head constraint (IRM). These missing comparisons are an empirical novelty risk, not proof that PIDR is superior.
6. **Explicit domain-adversarial loss?** No.
7. **Class labels?** No semantic class or safety labels. Condition metadata is used only by the sampler to construct audited control/treatment pairs. Universal capability state is an observable structured feature, not a safety label.
8. **One-to-one task matching?** The objective does not require exact task identity; pre-exposure candidates are selected by progress bin and compatible capability. Experiment 65's shuffled matching retained most of the pilot benefit, so strict semantic task correspondence was not the main training signal. This is development evidence, not a universal conclusion.
9. **Strongest defensible novelty sentence:**

> We formulate cross-agent-paradigm monitoring as a representation-transfer problem and study a lightweight objective that aligns audited pre-exposure delegation progression while preserving matched post-exposure intervention-associated variation in delayed paired trajectories.

10. **Forbidden novelty claims:**

- “PIDR introduces domain-invariant representation learning.”
- “PIDR is the first contrastive or intervention-aware representation learner.”
- “PIDR identifies causal latent authority states.”
- “PIDR solves cross-paradigm monitoring.”
- “PIDR achieves universal paradigm invariance.”
- “PIDR is DANN/CORAL/IRM but strictly better.”
- “DelegationBench is the first agent-security benchmark” without a separately verified priority search.

## Method-to-prior comparison

| Method | Domain alignment | Trajectory input | Intervention pairs | Preserves intervention difference | Security monitoring | Cross-agent paradigm evaluation |
|---|---|---|---|---|---|---|
| DANN [@ganin2016dann] | YES | NO | NO | NO | NO | NO |
| IRM [@arjovsky2019irm] | YES | NO | NO | PARTIAL | NO | NO |
| Deep CORAL [@sun2016deepcoral] | YES | NO | NO | NO | NO | NO |
| MMD/DAN [@long2015dan] | YES | NO | NO | NO | NO | NO |
| SelfReg [@kim2021selfreg] | YES | NO | NO | PARTIAL | NO | NO |
| PIDR-v1 | YES | YES | YES | YES | PARTIAL | YES |

“PARTIAL” for IRM means that an invariant predictor can retain task-discriminative variation through its supervised risk, but it has no explicit paired-intervention preservation term. “PARTIAL” for SelfReg means its class-specific positive-pair objective preserves class discrimination, not intervention differences. “PARTIAL” for PIDR security monitoring reflects that PIDR is a representation learner evaluated through a separate diagnostic monitor; downstream gains were inconclusive. The prior methods are mainly static classification methods, whereas PIDR consumes observable trajectory-prefix transitions.

## Closest methodological precedents

The closest generic baselines are **Deep CORAL** and **MMD/DAN** because they provide label-light distribution alignment without requiring a domain-adversarial classifier. DANN is the clearest test of explicit removal of paradigm information, but it requires a domain-classification head and is more complex. IRM is less well matched because DelegationBench does not supply a shared semantic prediction label for benign trajectory transitions. Weakly supervised causal representation learning [@brehmer2022weakcausal] is the closest precedent for extracting representation signal from paired interventions, but its target is identifiable causal variables under a generative model, not monitoring geometry in agent trajectories.

PIDR-v1's implementation is substantially simpler than these methods: signed SHA256-hashed unigram/bigram and structured features, learned diagonal scales, and L2 normalization. Its empirical result supports stronger post-exposure separation and lower paradigm-probe accuracy, not lower absolute benign distance or reliable detector improvement.

## Missing published baselines

### MUST_ADD

1. **Deep CORAL (Sun and Saenko, 2016).** Reviewers will expect a generic alignment method to test whether PIDR's outcome follows from ordinary second-order domain alignment. Adapt the frozen raw prefix vectors and align Coding/Web TRAIN-control covariances; retain the identical 5NN monitor and seed split. Feasible and low cost. It needs paradigm identity but no safety or intervention labels.
2. **MMD alignment / DAN-style loss (Long et al., 2015).** This is the strongest label-light distribution-alignment comparator because PIDR's pre-invariance term is distributionally motivated. Apply MMD to pre-exposure Coding/Web TRAIN prefixes, then use the frozen evaluation protocol. Feasible at moderate cost; no unavailable labels, although kernel/bandwidth choices must be fixed on development.
3. **DeepLog-style next-transition prediction (Du et al., 2017), adapted to observable agent events.** The current first-order Markov and tiny autoencoder baselines do not represent a competitive modern sequential normality model. Train only on TRAIN controls and use the same threshold protocol. Moderate cost; no safety labels required. It tests whether PIDR's apparent benefit is merely stronger sequential modeling.

### SHOULD_ADD

1. **DANN (Ganin et al., 2016).** Directly tests adversarial removal of paradigm identity. It is feasible, but the shared task objective must be chosen carefully; using intervention labels would violate the paper's label-free monitoring framing. A domain-only adversary plus reconstruction/temporal objective is defensible but is an adaptation, not vanilla DANN.
2. **Task Shield (Jia et al., 2025).** It is a published agent-security defense that checks action contribution to user goals. Adaptation to Coding/Web tools and offline scoring may be expensive; it tests task alignment rather than normality transfer, so report separately rather than in a single method leaderboard.
3. **AgentSpec or Progent.** These provide rule/privilege enforcement comparators. They require policies unavailable in the current label-free setup and answer a different question, but a small policy-aware comparison would clarify the tradeoff between learned normality and explicit specification.

### OPTIONAL

- IRM, because no natural shared class label exists.
- SelfReg, as a contrastive DG representative if a defensible positive-pair class is preregistered.
- LogAnomaly, if the DeepLog-style baseline remains too weak.
- A weakly supervised causal representation method only if the paper adds causal-latent claims; current claims do not justify that cost.

## Does the paper need a generic invariant-representation baseline?

**Yes.** The smallest scientifically defensible set is: Raw encoder + Deep CORAL + MMD + PIDR-v1, all feeding the same frozen transition kNN monitor. CORAL tests second-order alignment; MMD tests distribution matching; PIDR tests whether adding paired post-exposure preservation changes the tradeoff. DANN is a strong SHOULD_ADD rather than MUST_ADD because its task-classification assumptions do not cleanly fit the label-free benchmark. IRM is not a good minimal comparator without shared semantic labels.

## Baseline legitimacy and fairness conclusion

Action frequency, reconstruction, Markov, and kNN distance are canonical method families, but the repository implementations are adaptations, not direct reproductions. NDTR and C-NDTR are project-specific diagnostics. CDM is also project-specific and has access to matched normal references; it should not be placed on the same online-monitor axis without a conspicuous caveat. Raw+5NN and PIDR+5NN are the cleanest direct representation comparison because the downstream detector, source memory, and threshold protocol match. Their representation supervision differs intentionally: PIDR uses pair construction metadata during training.

CAAO is not a downstream monitor baseline. It uses paired post-hoc alignment and environment-exposure traces unavailable to an online monitor, so it belongs under dataset construction/oracle diagnostics.

## Recommended changes to Paper Draft v0.1

1. **Introduction:** replace broad “paradigm-invariant” novelty language with the recommended problem/combination sentence above.
2. **Baseline taxonomy:** cite canonical anomaly families and label NDTR/C-NDTR/CDM as project-specific diagnostics.
3. **Method:** add explicit contrasts to CORAL, MMD, DANN, and paired causal representation; state that PIDR has no adversarial head, class labels, covariance loss, or causal-identifiability claim.
4. **Related work:** insert the four-subsection draft in `RELATED_WORK_DRAFT.md` after claims are accepted.
5. **Limitations:** add absence of generic DG baselines as a submission-blocking limitation.
6. **Contributions:** make Benchmark/measurement primary until CORAL/MMD and a modern sequence model are evaluated.

## Provisional positioning

**A. BENCHMARK_MEASUREMENT_PRIMARY**

**Confidence: HIGH**

The benchmark has clean confirmatory evidence and a distinctive delayed paired design. PIDR-v1's composition is potentially novel, but its components have close established precedents, absolute benign alignment is not supported, downstream improvement is inconclusive, and generic domain-alignment baselines are missing. A representation-method-primary paper would be premature. The current defensible paper is a benchmark/measurement contribution with PIDR-v1 as a scoped proof of concept.
