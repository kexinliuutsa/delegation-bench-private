import pandas as pd
import subprocess
from pathlib import Path


df = pd.read_csv(
    "../results/delete_classification.csv"
)

cand = df[df["classification"]=="delete_preexisting"]


REPOS = {
    "lingua": "../repos/lingua-franca",
    "nipype": "../repos/nipype",
    "pydicom": "../repos/pydicom",
}


def check_file(repo, filename):

    result = subprocess.run(
        [
            "git",
            "-C",
            repo,
            "ls-files",
            filename
        ],
        capture_output=True,
        text=True
    )

    return bool(result.stdout.strip())


def repo_for_trace(trace):

    if "lingua" in trace:
        return "lingua"

    if "nipype" in trace:
        return "nipype"

    if "pydicom" in trace:
        return "pydicom"

    return None



print("="*80)
print("GIT TRACKING CHECK")
print("="*80)


for _, row in cand.iterrows():

    trace=row.trace
    action=row.action

    repo_name=repo_for_trace(trace)

    print("\n"+"-"*80)

    print("TRACE:")
    print(trace)

    print("ACTION:")
    print(action)

    if repo_name is None:
        print("NO REPO")
        continue


    repo=REPOS[repo_name]


    targets=[]

    for x in action.split()[1:]:

        if x.startswith("-"):
            continue

        targets.append(x)


    for target in targets:

        tracked=check_file(
            repo,
            target
        )

        print(
            target,
            "=>",
            "ORIGINAL FILE" if tracked else "NOT IN GIT"
        )

