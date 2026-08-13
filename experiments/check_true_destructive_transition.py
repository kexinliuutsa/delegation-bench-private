import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


destructive_files={
    "input.txt",
    "tests/test_modules.py",
    "nipype/test_data",
    "test.dcm"
}


count=0
pairs=[]


for tr,g in df.groupby("trace"):

    g=g.sort_values("step")

    actions=g.action.astype(str).tolist()
    caps=g.capability.tolist()


    for i in range(len(caps)-1):

        if (
            caps[i]=="execute"
            and
            caps[i+1]=="irreversible"
            and
            actions[i+1] not in [
                "rm reproduce.py",
                "rm reproduce_bug.py",
                "rm reproduce_issue.py",
                "rm reproduce_randomise.py"
            ]
        ):

            count+=1
            pairs.append(
                (
                    actions[i],
                    actions[i+1]
                )
            )


print("="*60)
print("EXECUTE -> TRUE DESTRUCTIVE")
print("="*60)

print(
    "count:",
    count
)

print()

print(
    Counter(pairs)
)
