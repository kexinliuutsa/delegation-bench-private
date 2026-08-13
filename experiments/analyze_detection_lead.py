import pandas as pd


df=pd.read_csv(
    "../results/static_vs_evolution_detection.csv"
)


print("="*70)
print("DETECTION TIMING ANALYSIS")
print("="*70)


# remove missing
valid=df[
    df.evolution_detection.notna()
    &
    df.impact_step.notna()
]


print(
    "evolution cases:",
    len(valid)
)


lead=(
    valid.impact_step
    -
    valid.evolution_detection
)


print()

print(
    "Evolution lead time"
)

print(
    lead.describe()
)


static_valid=df[
    df.static_detection.notna()
    &
    df.impact_step.notna()
]


static_delay=(
    static_valid.static_detection
    -
    static_valid.impact_step
)


print()

print(
    "Static detection relative to impact"
)

print(
    static_delay.describe()
)


print()

print(
    "saved summary"
)
