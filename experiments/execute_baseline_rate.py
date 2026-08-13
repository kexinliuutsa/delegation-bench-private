import pandas as pd


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


stats=[]


for trace,g in df.groupby("trace"):

    caps=set(
        g.capability
    )

    stats.append(
        {
            "trace":trace,
            "has_execute":
                "execute" in caps,
            "has_irreversible":
                "irreversible" in caps
        }
    )


r=pd.DataFrame(stats)


print("="*70)

print(
    "all trajectories execute rate:",
    r.has_execute.mean()
)


print(
    "with irreversible:",
    r[
        r.has_irreversible
    ].has_execute.mean()
)


print(
    "without irreversible:",
    r[
        ~r.has_irreversible
    ].has_execute.mean()
)

