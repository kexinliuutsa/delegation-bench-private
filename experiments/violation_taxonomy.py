import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


counts=Counter()


for trace,g in df.groupby("trace"):

    g=g.sort_values("step")

    caps=g.capability.tolist()


    if "irreversible" in caps:

        first_irrev=caps.index(
            "irreversible"
        )

        prefix=caps[:first_irrev+1]


        if "execute" in prefix:

            counts["execute_mediated_irreversible"]+=1

        else:

            counts["direct_irreversible"]+=1


    if "external" in caps:

        first_ext=caps.index(
            "external"
        )

        prefix=caps[:first_ext+1]


        if "execute" in prefix:

            counts["execute_mediated_external"]+=1

        else:

            counts["direct_external"]+=1



print("="*70)

for k,v in counts.items():
    print(k,v)

