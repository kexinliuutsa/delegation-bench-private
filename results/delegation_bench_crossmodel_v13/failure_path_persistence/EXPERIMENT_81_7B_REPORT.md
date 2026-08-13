# Experiment 81.7b — Failure-Path Raw Proposal Persistence Gate

Four offline **SYNTHETIC_DETERMINISTIC_FAILURE_FIXTURE** proposals exercised the production v1.3 `persist_proposal` hook. This is not historical failure reproduction. All 4 proposals remained parseable after downstream failure; append-only and event-ordering checks passed.

The automatic QC assertion distinguishes post-proposal failure (raw evidence required) from pre-proposal transport failure (no raw evidence expected). No model calls, scientific evaluation, smoke, or fresh-sealed access occurred.

Final status: **FAILURE_PATH_PERSISTENCE_VALIDATED**.
