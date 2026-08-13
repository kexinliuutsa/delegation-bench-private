# Pre-freeze quarantine

`v1_coding_C1_bug_fix_explicit_s03_treatment.json` completed during the
interrupt race of the failed pre-freeze collection attempt. It was generated
before the runner retry policy was added and before the current protocol hashes
were frozen, so it is excluded from every v1 manifest, status count,
normalization, measurement, and validity analysis.

- Original active path: `results/delegation_bench_v1/raw/v1_coding_C1_bug_fix_explicit_s03_treatment.json`
- SHA256: `2a7c2b1aafff16fa22332aae0860e200d29a5c415513253bf65f44902d0abe3c`
- Recovery: retained here verbatim; not deleted
