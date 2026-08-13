import pandas as pd
import random
from collections import Counter
import numpy as np


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


def clean(seq):

    r=[]

    for c in seq:
        if c=="unknown":
            continue

        if not r or r[-1]!=c:
            r.append(c)

    return r



trajectories=[]


for _,g in df.groupby("trace"):

    trajectories.append(
        clean(
            g.sort_values("step")
            .capability
            .tolist()
        )
    )



def transitions(trajs):

    c=Counter()

    for seq in trajs:

        for i in range(len(seq)-1):

            c[
                (seq[i],seq[i+1])
            ] += 1

    return c



obs=transitions(
    trajectories
)


targets=[
    ("execute","irreversible"),
    ("modify","irreversible"),
    ("execute","external")
]


for t in targets:

    print("="*60)

    print(t)

    print(
        "observed:",
        obs[t]
    )


    null=[]


    for _ in range(1000):

        shuffled=[]

        for seq in trajectories:

            x=seq.copy()
            random.shuffle(x)
            shuffled.append(x)


        null.append(
            transitions(shuffled)[t]
        )


    null=np.array(null)


    print(
        "null mean:",
        null.mean()
    )


    print(
        "95%:",
        np.percentile(
            null,
            [2.5,97.5]
        )
    )


    print(
        "p:",
        np.mean(
            null>=obs[t]
        )
    )

