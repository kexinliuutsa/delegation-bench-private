import pandas as pd
import numpy as np
from collections import defaultdict


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


df=df[
    df.capability!="unknown"
]


pairs=[
    ("execute","irreversible"),
    ("modify","irreversible"),
    ("execute","external")
]


def count_transition(data,a,b):

    count=0

    for _,g in data.groupby("trace"):

        caps=g.sort_values(
            "step"
        ).capability.tolist()


        for x,y in zip(caps,caps[1:]):

            if x==a and y==b:
                count+=1

    return count



runs=1000


for a,b in pairs:

    observed=count_transition(
        df,a,b
    )


    null=[]


    for i in range(runs):

        shuffled=[]

        for _,g in df.groupby("trace"):

            caps=g.capability.tolist()

            np.random.shuffle(caps)

            gg=g.copy()

            gg["capability"]=caps

            shuffled.append(gg)


        shuffled=pd.concat(
            shuffled
        )


        null.append(
            count_transition(
                shuffled,
                a,
                b
            )
        )


    null=np.array(null)


    p_enrich=(
        (null>=observed).sum()
        /
        runs
    )


    p_deplete=(
        (null<=observed).sum()
        /
        runs
    )


    print("="*60)

    print(
        f"{a}->{b}"
    )

    print(
        "observed:",
        observed
    )

    print(
        "null mean:",
        null.mean()
    )

    print(
        "95CI:",
        np.percentile(
            null,
            [2.5,97.5]
        )
    )

    print(
        "p enrich:",
        p_enrich
    )

    print(
        "p deplete:",
        p_deplete
    )
