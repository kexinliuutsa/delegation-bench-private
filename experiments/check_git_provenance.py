import pandas as pd
import os
import subprocess
import re
from pathlib import Path


DELETE_FILE = "../results/delete_classification.csv"


TRACE_ROOT = "../traces/public_swe_100"


df = pd.read_csv(DELETE_FILE)

cand = df[df["classification"]=="delete_preexisting"]


print("="*80)
print("GIT PROVENANCE CHECK")
print("="*80)


def get_repo_from_trace(trace):
    """
    Example:
    nipy__nipype-3325__swe-agent-llama-405b__0089

    repo:
    nipy/nipype
    """

    parts = trace.split("__")

    if len(parts) < 2:
        return None

    owner = parts[0]
    repo_part = parts[1]

    repo = repo_part.split("-")[0]

    return f"{owner}/{repo}"



def find_trace_file(trace):

    p = Path(TRACE_ROOT) / (trace + ".json")

    if p.exists():
        return p

    return None



def git_tracked(repo_dir, filename):

    try:

        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "ls-files",
                filename
            ],
            capture_output=True,
            text=True
        )

        return bool(result.stdout.strip())

    except Exception:

        return None



for _,row in cand.iterrows():

    trace=row["trace"]
    action=row["action"]

    print("\n"+"-"*80)

    print("TRACE:")
    print(trace)

    print("ACTION:")
    print(action)


    # extract rm targets

    targets=[]

    for x in action.split()[1:]:

        if x.startswith("-"):
            continue

        targets.append(x)


    print("TARGETS:")

    for t in targets:

        print(" ",t)


    repo=get_repo_from_trace(trace)

    print("repo guess:",repo)


    # locate trajectory folder

    trace_file=find_trace_file(trace)

    print("trace file:",trace_file)


print("\nNOTE:")
print("Need cloned SWE repositories to run git ls-files.")
print("Next step: provide repo root directory.")


