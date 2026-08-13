# Baseline Fairness Audit

All tunable methods had 24 frozen candidates. CORAL less budget than PIDR: NO. MMD less budget than PIDR: NO. DeepLog less budget than comparable sequence methods: NO in candidate count, but YES in architecture fidelity because PyTorch was unavailable and the implementation used a smoothed recurrent-history table rather than GRU/LSTM. TRAIN examples and seed-3 development selection were shared where applicable; seed 4 was not used for tuning. This weakens Q4 and prevents treating the sequence result as a faithful DeepLog reproduction.
