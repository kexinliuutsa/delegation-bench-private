import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


df=df[
    df.capability!="unknown"
]


pairs=[]


for trace,g in df.groupby("trace"):

    g=g.sort_values("step")

    rows=list(
        zip(
            g.step,
            g.capability
        )
    )


    for (s1,c1),(s2,c2) in zip(rows,rows[1:]):

        if (
            c1=="execute"
            and
            c2=="irreversible"
        ):
            pairs.append(
                s2-s1
            )


print("="*60)
print("EXECUTE -> IRREVERSIBLE STEP GAP")
print("="*60)


print(
    Counter(pairs)
)


print()

print(
    "total:",
    len(pairs)
)


print(
    "same step:",
    sum(
        x==0
        for x in pairs
    )
)

print(
    "next step:",
    sum(
        x==1
        for x in pairs
    )
)
