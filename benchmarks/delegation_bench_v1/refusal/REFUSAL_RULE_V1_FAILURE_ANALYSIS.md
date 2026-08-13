# Refusal Rule v1 Failure Analysis

The frozen v1 rule was not changed. This document records synthetic semantic families missed before any future v2 is considered.

- ABSTAIN / `ambiguous_clarification_hard_negative`: 1
- ABSTAIN / `ambiguous_hesitation`: 2
- ABSTAIN / `ambiguous_hesitation_hard_negative`: 1
- ABSTAIN / `ambiguous_object_hard_negative`: 1
- ABSTAIN / `ambiguous_planning`: 1
- ABSTAIN / `ambiguous_question_hard_negative`: 1
- ABSTAIN / `environment_or_resistance_hard_negative`: 1
- ABSTAIN / `inability_or_refusal_ambiguous_hard_negative`: 1
- ABSTAIN / `mixed_environment_hard_negative`: 1
- ABSTAIN / `mixed_inability_hard_negative`: 1
- ABSTAIN / `planning_or_hesitation_hard_negative`: 1
- ABSTAIN / `underspecified`: 2
- ABSTAIN / `weak_hesitation_ambiguous`: 1
- CONTINUE / `inability_hard_negative`: 1
- CONTINUE / `routine_planning_hard_negative`: 2
- HESITATE / `explicit_caution`: 2
- HESITATE / `explicit_concern`: 2
- HESITATE / `explicit_risk`: 1
- HESITATE / `explicit_uncertainty`: 1
- HESITATE / `paraphrased_hesitation`: 5
- REFUSE / `behavioral_refusal`: 1
- REFUSE / `decline_paraphrase`: 2
- REFUSE / `not_going_paraphrase`: 1
- REFUSE / `paraphrased_refusal`: 3
- REQUEST_CONFIRMATION / `clarification_before_action`: 1
- REQUEST_CONFIRMATION / `conditional_confirmation`: 1
- REQUEST_CONFIRMATION / `confirmation_question`: 1
- REQUEST_CONFIRMATION / `explicit_approval`: 1
- REQUEST_CONFIRMATION / `paraphrased_confirmation`: 4
- REQUEST_CONFIRMATION / `permission_question`: 1
- REQUEST_CONFIRMATION / `proceed_question`: 1

No Phase-0 examples were relabeled or rerun. Any improved classifier must be separately versioned as v2.
