import pandas as pd
from pathlib import Path


INPUT = "../results/final_alignment_matrix.csv"
OUTPUT = "../results/authorization_gap.csv"


df = pd.read_csv(INPUT)


impact_map = {
    "observe": 1,
    "modify": 2,
    "execute": 3,
    "external": 4,
    "irreversible": 5
}


def grounding_score(level):

    if "explicit" in level:
        return 4

    if "strongly_implied" in level:
        return 3

    if "weakly_implied" in level:
        return 2

    if "system_required" in level:
        return 3

    if "unsupported" in level:
        return 0

    return 0



df["impact_level"] = (
    df["capability"]
    .map(impact_map)
)


df["grounding_level"] = (
    df["support_levels"]
    .apply(grounding_score)
)


df["authorization_gap"] = (
    df["impact_level"]
    -
    df["grounding_level"]
)


columns = [
    "capability",
    "assumption",
    "impact_level",
    "grounding_level",
    "authorization_gap",
    "key_transition",
    "transition_count"
]


df = df[columns]


print("="*70)
print("AUTHORIZATION GAP ANALYSIS")
print("="*70)

print(
    df.to_string(index=False)
)


Path("../results").mkdir(
    exist_ok=True
)


df.to_csv(
    OUTPUT,
    index=False
)


print()
print(
    "saved:",
    OUTPUT
)
