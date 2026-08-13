# Open Questions

## RESOLVED

1. **Baseline provenance.** Action frequency, reconstruction, Markov, and transition kNN are canonical families implemented as project-specific adaptations. NDTR, C-NDTR, and CDM are project-specific diagnostics; CDM is not directly comparable to an online monitor.
2. **Method novelty category.** Domain invariance, benign alignment, and pairwise margin separation are established. The potentially novel element is the delayed paired trajectory-security problem and the particular align-benign/preserve-intervention combination.
3. **Current positioning.** Benchmark/measurement primary, PIDR-v1 as proof of concept. Representation-method-primary positioning is not yet supported.
4. **Human labels for retained claims.** They are not required for operational paired divergence and representation geometry; they would be required for authorization, unsafe-action, or malicious-intent claims, which the draft excludes.

## MUST_RESOLVE_BEFORE_SUBMISSION

1. Validate the lightweight CORAL/MMD/DeepLog adaptations against reference implementations if the target venue expects implementation-level fidelity; current comparisons use shared dependency-light adaptations.
2. Map the final paper prose to verified citation keys and perform a venue-specific search update near submission.
3. Decide whether the paper title should retain “delegation” or use the narrower “intervention-sensitive behavioral representation,” given the absence of authorization ground truth.
4. Confirm that the exact encoder implementation—signed SHA256 hashing, diagonal scaling, scale clamping, and L2 normalization—is described mathematically and not as a generic learned linear projection.
5. Add uncertainty for any v0 pilot baseline numbers retained in a main table, or move them to motivation/appendix with an explicit missing-CI caveat.
6. Decide whether the target venue accepts a two-paradigm core benchmark; a third paradigm remains untested and cannot support current claims.
7. Clarify the status of recent runtime-enforcement comparators (Task Shield, AgentSpec, Progent) and whether one scoped policy-based comparison is expected by the target venue.

## OPTIONAL

- DANN, if a label-free auxiliary objective can be preregistered without changing the research question.
- PIDR-v2 with a different objective addressing absolute pre-benign distance.
- A genuinely new sealed test; seed 4 cannot be reused.
- A mature third real paradigm and a distinct underlying model family.
- A stronger, preregistered downstream monitor.
- Human authorization annotation with inter-rater agreement.
- Larger samples for task/style heterogeneity.
- Update the corpus with strong archival 2026 work before submission.

Highest-priority issue: **cross-model replication and reference-implementation validation are now more important than another PIDR iteration on the opened seed-4 set.**
