import pandas as pd


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


def extract_model(trace):

    parts = trace.split("__")

    for p in parts:

        if "swe-agent" in p:
            return p

    return "unknown"



df["model"] = df.trace.apply(
    extract_model
)


print(
    df.model.value_counts()
)


print("="*80)
print("MODEL EXECUTE -> IRREVERSIBLE")
print("="*80)



for model,g in df.groupby("model"):

    count=0
    traces=0


    for trace,t in g.groupby("trace"):

        caps=(
            t.sort_values("step")
            .capability
            .tolist()
        )


        caps=[
            x for x in caps
            if x!="unknown"
        ]


        hit=False

        for i in range(len(caps)-1):

            if (
                caps[i]=="execute"
                and
                caps[i+1]=="irreversible"
            ):
                hit=True


        if hit:
            count+=1


        traces+=1


    print(
        model,
        "trajectories:",
        traces,
        "execute->irreversible:",
        count,
        "rate:",
        round(count/traces,3)
    )
