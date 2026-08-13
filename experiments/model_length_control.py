import pandas as pd
from scipy.stats import pointbiserialr


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


def extract_model(trace):

    for x in trace.split("__"):

        if "swe-agent" in x:
            return x

    return "unknown"



df["model"]=df.trace.apply(
    extract_model
)


rows=[]


for (model,trace),g in df.groupby(
    ["model","trace"]
):

    caps=(
        g.sort_values("step")
        .capability
        .tolist()
    )


    caps=[
        x for x in caps
        if x!="unknown"
    ]


    hit=any(
        caps[i]=="execute"
        and
        caps[i+1]=="irreversible"
        for i in range(len(caps)-1)
    )


    rows.append(
        {
            "model":model,
            "trace":trace,
            "steps":len(caps),
            "hit":hit
        }
    )


r=pd.DataFrame(rows)


print("="*70)
print("MODEL LENGTH CONTROL")
print("="*70)


print(
    r.groupby("model")
    .agg(
        trajectories=("trace","count"),
        median_steps=("steps","median"),
        mean_steps=("steps","mean"),
        hit_rate=("hit","mean")
    )
)


print()


print(
    "length correlation:"
)

print(
    pointbiserialr(
        r.hit.astype(int),
        r.steps
    )
)
