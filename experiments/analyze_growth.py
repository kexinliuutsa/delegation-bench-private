import pandas as pd


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


summary=(

df.groupby("trace")

.agg(
    initial_level=(
        "level",
        "first"
    ),

    final_level=(
        "level",
        "max"
    ),

    steps=(
        "step",
        "max"
    )
)

)


summary["growth"]=(
    summary.final_level
    -
    summary.initial_level
)


print(summary.describe())


print()

print(
    "growth distribution"
)

print(
    summary.growth.value_counts()
)


summary.to_csv(
    "../results/authority_growth.csv"
)

