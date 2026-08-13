import pandas as pd


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


df=df[
    df.capability!="unknown"
]


rows=[]


for trace,g in df.groupby("trace"):

    g=g.sort_values("step")

    caps=g.capability.tolist()

    if "irreversible" in caps:

        pos=caps.index("irreversible")

        rows.append(
            pos/(len(caps)-1)
        )


print("trajectories:",len(rows))

print(
    pd.Series(rows).describe()
)
