# Retry and Failure Policy

Pre-proposal transport/API failures are retryable with missing-only resume. Completed trajectories are never rerun. Post-proposal failures require raw proposal evidence through the Experiment-81.7b assertion. Corrupt/partial trajectories are quarantined and only that incomplete job may rerun without scientific changes. Raw proposal persistence is required for 100% of received proposals.
