# PIDR-v1 Method

PIDR-v1 (Paradigm-Invariant Delegation Representation v1) is a representation learner, not a detector. A separate, fixed 5NN transition-distance monitor is used only as a development diagnostic.

## Input and encoder

The representation unit is an observable trajectory-prefix transition. Its whitelisted inputs are task text, paradigm, prior observable actions/tools/observations/capabilities, current observation and source, current action/tool/capability, normalized progress, and recent action/tool run lengths. Condition, intervention style, pair identifiers, exposure schedule, future events, labels, and private reasoning are excluded.

Text and action content is encoded with deterministic signed SHA256-hashed unigrams and bigrams. Structured categorical and scalar features are added to the same sparse representation. A learned linear diagonal projection produces a 128-dimensional vector, followed by L2 normalization. No external embedding API or deep network is used.

## Sampling and objective

Pre-exposure invariance samples use prefixes strictly before reconstructed exposure. Samples are balanced across progress-bin and compatible universal capability, pairing Coding and Web when possible; exact task identity is not required. Audited pre-exposure prefixes from both pair conditions may be used because the intervention was not observable.

Post-exposure sensitivity samples exist only for pairs with reconstructed actual exposure. Control/treatment transitions are aligned monotonically by normalized progress. Condition metadata is used by this sampler solely to construct matched pairs and never enters the encoder.

Temporal samples are adjacent prefixes within one trajectory when capability is unchanged and no exposure boundary is crossed. Variance preservation clamps learned projection scales to a target standard-deviation floor, preventing trivial collapse.

The exact objective is:

`L = L_pre_invariance + lambda_sep L_post_sensitivity + beta_temp L_temporal_consistency + gamma_var L_variance`

`L_pre_invariance` minimizes squared aligned distance. `L_post_sensitivity` is a margin loss that preserves matched post-exposure differences. `L_temporal_consistency` reduces ordinary within-state local noise. `L_variance` uses target standard deviation 0.05 as a collapse-prevention regularizer.

## Train/development/test isolation

TRAIN uses Coding and Web seeds 0, 1, and 2. DEVELOPMENT uses seed 3. Twenty-four deterministic configurations were evaluated in two stages: dimension × separation weight, followed by temporal weight × margin around the best Stage-1 configuration. Selection used a fixed rank aggregation of separation/alignment ratio, pre-benign distance, development AUROC, and development false alarm. The 5NN threshold was calibrated from TRAIN controls only.

Seed 4 remains sealed. Training and evaluation loaders hard-abort on seed 4 and log every opened trajectory path. PIDR-v1 does not jointly train a prediction head or detector, and no supervised intervention classifier is fitted.

## Development interpretation

PIDR-v1 increases post/pre geometric separation and improves the fixed-monitor diagnostics without latent collapse. It lowers paradigm-probe accuracy, indicating partial removal of paradigm-specific information. It does not lower absolute cross-paradigm pre-benign distance in this development result, so no stronger alignment claim is made before sealed testing.
