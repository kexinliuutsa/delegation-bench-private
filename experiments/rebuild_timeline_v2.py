import json
import glob
import re
import pandas as pd
from pathlib import Path


TRACE_DIR = "../traces/public_swe_100"

OUTPUT = "../results/authority_timeline_v2.csv"


def extract_commands(text):

    if not text:
        return []

    commands=[]

    # extract markdown code blocks
    blocks = re.findall(
        r"```(?:bash|sh|shell)?\s*\n?(.*?)```",
        text,
        flags=re.S
    )

    for b in blocks:

        for line in b.split("\n"):

            line=line.strip()

            if line:
                commands.append(line)

    return commands



def classify(cmd):

    text=cmd.lower()

    # benchmark submission
    if text.strip()=="submit":
        return "submission"


    # deletion
    if (
        text.startswith("rm ")
        or text.startswith("rm\t")
    ):
        return "irreversible"


    # external
    if any(
        x in text
        for x in [
            "curl ",
            "wget ",
            "email",
            "api"
        ]
    ):
        return "external"


    # execution
    if any(
        x in text
        for x in [
            "python ",
            "pytest",
            "bash ",
            "sh ",
            "make "
        ]
    ):
        return "execute"


    # modify
    if any(
        x in text
        for x in [
            "edit ",
            "write ",
            "patch "
        ]
    ):
        return "modify"


    # observe
    if any(
        x in text
        for x in [
            "open ",
            "cat ",
            "ls ",
            "grep ",
            "find_file",
            "search_dir"
        ]
    ):
        return "observe"


    return "unknown"



rows=[]


files=glob.glob(
    TRACE_DIR+"/*.json"
)


print("files:",len(files))


for f in files:

    with open(f) as x:
        data=json.load(x)


    trace=Path(f).stem


    step=0


    for item in data["trajectory"]:

        if item.get("role")!="ai":
            continue


        commands=extract_commands(
            item.get("text")
        )


        for cmd in commands:

            rows.append(
                {
                    "trace":trace,
                    "step":step,
                    "action":cmd,
                    "capability":classify(cmd)
                }
            )

            step+=1



df=pd.DataFrame(rows)


print()
print("="*70)
print(df.capability.value_counts())
print("="*70)


Path(
    "../results"
).mkdir(
    exist_ok=True
)


df.to_csv(
    OUTPUT,
    index=False
)


print("saved:",OUTPUT)
