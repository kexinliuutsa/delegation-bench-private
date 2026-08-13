import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


df=df[
    df.capability!="unknown"
]


transitions=[
    ("execute","irreversible"),
    ("modify","irreversible"),
    ("execute","external"),
]


print("="*80)
print("TRANSITION VALIDITY CHECK")
print("="*80)



for src,dst in transitions:

    gaps=[]

    examples=[]


    for trace,g in df.groupby("trace"):

        g=g.sort_values("step")


        rows=list(
            zip(
                g.step,
                g.capability
            )
        )


        for (s1,c1),(s2,c2) in zip(rows,rows[1:]):

            if c1==src and c2==dst:

                gaps.append(
                    s2-s1
                )

                examples.append(
                    trace
                )


    print()
    print("-"*60)
    print(
        f"{src} -> {dst}"
    )

    print(
        "count:",
        len(gaps)
    )

    print(
        "gap distribution:",
        Counter(gaps)
    )

    print(
        "same step:",
        sum(x==0 for x in gaps)
    )

    print(
        "valid next-step:",
        sum(x>=1 for x in gaps)
    )
