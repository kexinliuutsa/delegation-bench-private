import pandas as pd
import re


df=pd.read_csv(
    "../results/authority_timeline_v2.csv"
)

df=df.sort_values(
    ["trace","step"]
)


def extract_path(action):

    tokens=str(action).split()

    if len(tokens)<2:
        return None

    for t in tokens[1:]:

        if t.startswith("-"):
            continue

        if t.isdigit():
            continue

        return t.strip("`")

    return None



rows=[]


for trace,g in df.groupby("trace"):

    current_file=None
    created=set()


    for _,r in g.iterrows():

        action=str(r.action).strip()

        head=action.split()[0] if action else ""


        path=extract_path(action)


        # track current editor file
        if head in [
            "open",
            "goto"
        ] and path:

            current_file=path


        # created artifact
        if head=="create" and path:

            created.add(path)


        # edit affects current file
        if head=="edit" and current_file:

            created.add(current_file)


        # classify rm
        if action.startswith("rm "):

            target=extract_path(action)

            if target in created:

                label="cleanup"

            else:

                label="delete_preexisting"


            rows.append(
                {
                    "trace":trace,
                    "step":r.step,
                    "action":action,
                    "target":target,
                    "classification":label,
                    "created_files":";".join(sorted(created))
                }
            )



res=pd.DataFrame(rows)


print("="*70)
print("DELETE CLASSIFICATION")
print("="*70)

print(
    res.classification.value_counts()
)


print()
print("DELETE PREEXISTING:")
print(
    res[
        res.classification=="delete_preexisting"
    ][
        [
            "trace",
            "step",
            "action",
            "created_files"
        ]
    ]
    .to_string(index=False)
)


res.to_csv(
    "../results/delete_classification.csv",
    index=False
)


print()
print("saved")
