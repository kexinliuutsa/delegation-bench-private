import pandas as pd


df=pd.read_csv(
    "../results/static_vs_evolution_detection.csv"
)


static_only=df[
    df.static_detection.notna()
    &
    df.evolution_detection.isna()
]


print("="*70)
print("STATIC ONLY CASES")
print("="*70)

print(
    "count:",
    len(static_only)
)


print(
    static_only.trace.tolist()
)


print()
print("done")
