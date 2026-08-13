# Terminology

- **Delegation evolution:** observable change in the sequence of capabilities/actions an agent exercises during a task. It is an analysis abstraction, not authorization ground truth.
- **Trajectory divergence:** normalized difference between paired observable action or capability sequences.
- **Intervention-associated divergence:** post-exposure paired divergence measured under the randomized environmental intervention protocol.
- **Benign path variation:** control/treatment path differences arising before intervention is observable under generation-isolated conditions.
- **Paradigm:** an execution interface and action/observation regime, such as Coding or Web.
- **Control:** the paired condition receiving the matched benign environment observation.
- **Treatment:** the paired condition receiving the declared environmental intervention through the ordinary observation channel; treatment is not automatically malicious.
- **Exposure:** the first trajectory step at which the intervention payload is observable.
- **Pre-exposure:** observable execution strictly before reconstructed actual exposure.
- **Post-exposure:** execution from reconstructed actual exposure onward.
- **Capability sequence:** the ordered universal capability tiers associated with observed actions.
- **PIDR:** Paradigm-Invariant Delegation Representation, a representation learner using observable trajectory-prefix transitions.
- **Model-selection-sealed test:** the fixed seed-4 split opened once after PIDR-v1 development; it is now opened and cannot be reused as sealed evidence.

## Required distinctions

- Trajectory divergence **is not** unsafe behavior.
- Intervention-associated divergence **is not** an authority violation.
- Representation separation **is not** detector success.
- Paradigm invariance **is not** universal generalization.
