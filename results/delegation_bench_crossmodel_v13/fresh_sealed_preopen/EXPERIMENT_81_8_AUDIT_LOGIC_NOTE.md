# Experiment 81.8 Audit-Logic Correction Note

One Batch-B GPT-5 trajectory initially experienced a **PRE-PROPOSAL HTTP 403 transport failure**. The frozen missing-only resume policy retried only that missing trajectory, and the retry completed successfully. The historical failure artifact remained on disk. The initial audit implementation mistakenly treated existence of that historical failure JSON as an active failure after valid trajectory persistence. Audit bookkeeping was corrected to define `active_failure = failure_record_exists AND trajectory_output_missing`.

No raw trajectory changed, no completed trajectory was rerun, no scientific metric was inspected, and the correction affected audit bookkeeping only.
