import pandas as pd


df=pd.read_csv(
    "../results/delete_classification.csv"
)


cand=df[
    df.classification=="delete_preexisting"
]


print("="*80)

for _,r in cand.iterrows():

    print()
    print("="*80)

    print("TRACE:")
    print(r.trace)

    print()

    print("STEP:")
    print(r.step)

    print()

    print("ACTION:")
    print(r.action)

    print()

    print("CREATED FILES:")
    print(r.created_files)


print()
print("count:",len(cand))
