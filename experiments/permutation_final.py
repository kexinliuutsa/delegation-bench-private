import pandas as pd
import numpy as np


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


df=df[
    df.capability!="unknown"
]


TARGETS=[
    ("execute","irreversible"),
    ("modify","irreversible"),
    ("execute","external"),
]


def count_transition(caps,src,dst):

    return sum(
        caps[i]==src and caps[i+1]==dst
        for i in range(len(caps)-1)
    )


trajectories=[]


for trace,g in df.groupby("trace"):

    caps=(
        g.sort_values("step")
        .capability
        .tolist()
    )

    trajectories.append(caps)



for src,dst in TARGETS:

    observed=sum(
        count_transition(c,src,dst)
        for c in trajectories
    )


    null=[]


    for _ in range(1000):

        total=0

        for c in trajectories:

            shuffled=c.copy()

            np.random.shuffle(
                shuffled
            )

            total+=count_transition(
                shuffled,
                src,
                dst
            )

        null.append(total)


    null=np.array(null)


    print("="*60)
    print(
        src,
        "->",
        dst
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
        "95%:",
        np.percentile(
            null,
            [2.5,97.5]
        )
    )

    print(
        "p:",
        (null>=observed).mean()
    )
