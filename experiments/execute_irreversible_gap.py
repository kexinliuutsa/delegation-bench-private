import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)

gaps=Counter()


for trace,g in df.groupby("trace"):

    caps=(
        g.sort_values("step")
        .capability
        .tolist()
    )


    if "irreversible" not in caps:
        continue


    irr=caps.index("irreversible")


    before=caps[:irr]


    if "execute" in before:

        last_execute = (
            len(before)-1-before[::-1].index("execute")
        )

        gap=irr-last_execute

        gaps[gap]+=1



print("="*70)
print("EXECUTE -> IRREVERSIBLE GAP")

for k,v in sorted(gaps.items()):
    print(k,v)

