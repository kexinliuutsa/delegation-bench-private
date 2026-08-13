# Limitations Register

| # | Limitation | Severity | Affects claims | Mitigation | Future experiment |
|---:|---|---|---|---|---|
| 1 | Only Coding and Web core paradigms | High | Breadth and paradigm generalization | Limit claims to this paradigm pair | Add an independently validated third real paradigm |
| 2 | Same underlying GPT-5 model | High | Model-family generality | State architecture/model coupling | Repeat protocol with a distinct model family |
| 3 | Third paradigm not evaluated | High | Universal invariance | Future domain remains UNASSIGNED | Pre-register a new external transfer study |
| 4 | 27 Web pairs did not reach exposure | Medium | Temporal PRE/POST sample composition | Retain them; never fabricate POST data | Design tasks with higher exposure reach without changing v1 |
| 5 | Pre-exposure stochastic divergence is substantial | Medium | Anomaly interpretation | Stratified audit and pseudo-pair sensitivity | Replicate with deterministic decoding or paired replay |
| 6 | PIDR does not reduce absolute pre-benign distance | High | Benign-alignment claim | Mark C9 NOT_SUPPORTED | Develop a new method and new sealed test |
| 7 | Downstream monitoring improvement is inconclusive | High | Detector/deployment claims | Treat PIDR as representation learner | Evaluate a preregistered monitor on new data |
| 8 | Operational divergence is not unsafe-behavior ground truth | High | Security impact | Use intervention-associated divergence terminology | Add independent safety annotations if needed |
| 9 | No human authorization labels | High | Delegation/authorization claims | Avoid authorization-violation conclusions | Human annotation with agreement audit |
| 10 | No claim about internal reasoning | Medium | Mechanistic interpretation | Use observable trajectories only | Independent mechanistic study, if ethically available |
| 11 | Mock GUI excluded from final benchmark | Low | Three-domain breadth | Clearly mark GUI unused | Select a mature real GUI environment |
| 12 | Seed 4 is opened and cannot be reused for PIDR-v2 | High | Future model selection | Preserve one-shot marker | Collect a genuinely new sealed test |

Additional limitations include small per-cell heterogeneity samples, mock/sandboxed external effects, a simple diagonal projection, incomplete related-work mapping, and the absence of human judgments about whether observed changes are desirable.

## Cross-model replication limitation

Fresh-sealed replication could not be completed because provider quota exhaustion truncated the gpt-4.1 cohort at 68/80 trajectories (with one additional HTTP transport failure). Although aggregate effective N remained large, missingness removed the `transaction_preparation` task family entirely from complete pairs, preventing a valid paired secondary analysis. The cross-model hypothesis is neither confirmed nor falsified.
