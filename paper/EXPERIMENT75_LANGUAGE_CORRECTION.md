# Experiment 75 Language Correction

PIDR-v1 exhibits significantly stronger post-exposure representation separation than CORAL/MMD on the previously opened evaluation set, consistent with selective intervention-sensitive representation geometry. However, this did not translate into better downstream detection: PIDR's point-estimate detection rate was 34.38%, no better than MMD and below RAW's 40.63%, while PIDR was the only method with a non-zero benign false-alarm rate (3.13%). AUROC differences were not statistically resolved. We therefore treat PIDR-v1 as a representation-level proof-of-concept whose downstream monitoring utility remains unestablished.

The sequence baseline is a **dependency-light DeepLog-style recurrent-history diagnostic**, not a faithful DeepLog reproduction. Our lightweight next-event sequence diagnostic did not show incremental value; a faithful DeepLog/reference sequence-model comparison remains future work. We do not infer that published DeepLog is ineffective or that modern sequence modeling cannot explain the effect.

Seed 4 is a previously opened existing evaluation set and Experiment 75 is a retrospective published-baseline comparison, not confirmatory evidence.
