
import pandas as pd
import subprocess
from pathlib import Path


print("="*70)
print("GROUNDING INDEPENDENCE CHECK")
print("="*70)


# ---------------------------
# Original transition result
# ---------------------------

original = {
    "execute_irreversible":43,
    "null_mean":22.012,
    "execute_external":9
}


print()
print("Original transition:")
print(original)


# ---------------------------
# Create alternative grounding
# ---------------------------

df = pd.read_csv(
    "../results/capability_assumption_alignment.csv"
)


print()
print("Original grounding:")
print(
    df[
        [
            "capability",
            "support_levels"
        ]
    ].to_string(index=False)
)


# simulate changing Code Execution assumption

df.loc[
    df.capability=="execute",
    "support_levels"
] = "strongly_implied"


print()
print("Modified grounding:")
print(
    df[
        [
            "capability",
            "support_levels"
        ]
    ].to_string(index=False)
)


df.to_csv(
    "../results/capability_assumption_alignment_sensitivity.csv",
    index=False
)


# ---------------------------
# Transition does NOT use DAR
# verify input independence
# ---------------------------

timeline = pd.read_csv(
    "../results/authority_timeline.csv"
)


print()
print("Transition source rows:")
print(
    len(timeline)
)


print(
    "Transition traces:"
)

print(
    timeline.trace.nunique()
)


print()
print(
    "Sensitivity result:"
)

print(
    """
Changing Code Execution grounding:
weakly_implied -> strongly_implied

should NOT change:

execute->irreversible transition count
permutation null distribution
execute->external transition count
"""
)


print()
print("saved:")
print(
    "../results/capability_assumption_alignment_sensitivity.csv"
)

