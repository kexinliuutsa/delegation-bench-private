import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


counter=Counter()


traj_count=Counter()


for trace,g in df.groupby("trace"):

    g=g.sort_values("step")

    caps=g.capability.tolist()


    for i in range(len(caps)-1):

        if (
            caps[i]=="execute"
            and
            caps[i+1]=="irreversible"
        ):
            counter["execute->irreversible_adjacent"] += 1
            traj_count["traj_with_execute_irreversible"] += 1
            break


    if "irreversible" in caps:

        idx=caps.index("irreversible")

        prefix=caps[:idx]

        if "execute" in prefix:
            traj_count["irreversible_with_any_execute"] += 1



print("="*70)

print("transition count:")
print(counter)

print()

print("trajectory count:")
for k,v in traj_count.items():
    print(k,v)

