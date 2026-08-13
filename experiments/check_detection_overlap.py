import pandas as pd


df=pd.read_csv(
    "../results/static_vs_evolution_detection.csv"
)


static=set(
    df[
        df.static_detection.notna()
    ].trace
)


evolution=set(
    df[
        df.evolution_detection.notna()
    ].trace
)


print("="*60)

print(
    "static:",
    len(static)
)

print(
    "evolution:",
    len(evolution)
)


print(
    "evolution subset of static:",
    evolution.issubset(static)
)


print(
    "overlap:",
    len(static & evolution)
)


print(
    "evolution only:",
    evolution-static
)


print(
    "static only:",
    len(static-evolution)
)
