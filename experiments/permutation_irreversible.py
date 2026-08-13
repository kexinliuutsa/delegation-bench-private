import pandas as pd
import random
import numpy as np


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


def compress(caps):

    result=[]

    for c in caps:

        if c=="unknown":
            continue

        if not result or c!=result[-1]:
            result.append(c)

    return result



def first_irreversible(seq):

    if "irreversible" not in seq:
        return None

    return (
        seq.index("irreversible")
        /
        len(seq)
    )



observed=[]

trajectories=[]


for trace,g in df.groupby("trace"):

    caps=compress(
        g.sort_values("step")
        .capability
        .tolist()
    )

    trajectories.append(caps)

    pos=first_irreversible(caps)

    if pos is not None:
        observed.append(pos)



print("="*80)
print("OBSERVED")
print("="*80)

print(
    "trajectories:",
    len(trajectories)
)

print(
    "with irreversible:",
    len(observed)
)

print(
    "mean position:",
    np.mean(observed)
)



# permutation

null=[]


for _ in range(1000):

    positions=[]


    for caps in trajectories:

        shuffled=caps.copy()

        random.shuffle(
            shuffled
        )

        pos=first_irreversible(
            shuffled
        )

        if pos is not None:
            positions.append(pos)


    if positions:

        null.append(
            np.mean(positions)
        )



null=np.array(null)


print()
print("="*80)
print("NULL DISTRIBUTION")
print("="*80)


print(
    "mean:",
    null.mean()
)


print(
    "95% interval:",
    np.percentile(
        null,
        [2.5,97.5]
    )
)


print()


p=(
    np.sum(
        null <= np.mean(observed)
    )
    /
    len(null)
)


print(
    "p-value:",
    p
)

