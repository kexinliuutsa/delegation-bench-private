# Search Log

Search date: **2026-08-12**. Search engines/databases: web search over primary publisher pages (ACM/USENIX/ACL Anthology/PMLR/JMLR/OpenReview/ICLR/NeurIPS/CVF), exact-title searches, and arXiv only where no archival record was found. Technical conclusions were retained from primary paper pages, not blogs.

## Queries and retention

| Area | Representative queries | Papers inspected | Retained |
|---|---|---:|---:|
| Agent security | `LLM agent runtime monitor`; `agent trajectory safety monitoring`; `agent policy enforcement`; exact ToolEmu/AgentSpec/Progent searches | 14 | 6 |
| Environmental injection | `indirect prompt injection agents`; `web agent prompt injection`; `tool agent untrusted observation`; exact AgentDojo/InjecAgent/Greshake searches | 13 | 5 |
| Sequence anomaly | `sequence anomaly detection autoencoder`; `Markov sequence anomaly`; `nearest neighbor outlier`; `DeepLog`; `LogAnomaly` | 15 | 5 |
| Domain generalization | `DANN`; `Deep CORAL`; `MMD domain alignment`; `IRM`; `contrastive domain generalization`; `DomainBed` | 18 | 7 |
| Intervention-aware representation | `weakly supervised causal representation`; `paired intervention representation`; `interventional causal representation learning` | 11 | 4 |
| Cross-environment agents | `SWE-bench`; `BrowserGym`; `OSWorld`; `agent cross environment generalization` | 12 | 3 |

Total retained in the map: **30**. Category counts overlap conceptually only when discussed in prose; every map row has one primary area.

## Exclusion notes

- **AGENT-SAFETYBENCH, SEC-bench, AdvCLI, and several 2025–2026 workshop/preprint benchmarks:** relevant-looking but excluded to avoid padding; ASB, ToolEmu, AgentDojo, and InjecAgent already cover the needed benchmark axes with stronger archival status.
- **GuardAgent:** inspected, but the retained source was a project page and the exact archival metadata was not sufficiently clear in this pass.
- **IPIGuard and AgentVigil:** relevant recent defenses/red-teaming systems, but not necessary for the minimum map after retaining Task Shield, AgentDojo, and InjecAgent.
- **VIGIL and Pro2Guard:** highly relevant recent preprints, but too recent and non-archival for the core map; retain as future-update candidates.
- **BrowserGym arXiv version:** replaced with the TMLR archival record.
- **IRM:** retained as arXiv because the canonical work has no archival conference version.
- **Deep CORAL:** retained with its ECCV Workshop identity and arXiv landing page; no venue detail was invented beyond the paper record.
- **Generic transfer-learning surveys and blog explanations:** excluded in favor of DANN, CORAL, DAN, IRM, DomainBed, SelfReg, and primary causal-representation papers.
- **Causal Triplet and newer causal-representation variants:** inspected but excluded because Brehmer, Locatello, Ahuja, and von Kügelgen cover the methodological issue without inflating the bibliography.
- **Generalist agent capability benchmarks beyond SWE-bench, BrowserGym, and OSWorld:** excluded because they compare task success, not security-monitor transfer.

## Reproducibility caveat

Search completeness cannot prove that no direct precedent exists. The novelty wording therefore uses “we found limited evaluation” and records the missing generic baselines. A venue-specific update should repeat the search close to submission.
