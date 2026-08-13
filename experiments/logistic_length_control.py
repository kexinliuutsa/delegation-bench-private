import pandas as pd
import statsmodels.api as sm


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


rows=[]


for trace,g in df.groupby("trace"):

    caps=(
        g.sort_values("step")
        .capability
        .tolist()
    )


    caps=[
        c for c in caps
        if c!="unknown"
    ]


    hit=any(
        caps[i]=="execute"
        and
        caps[i+1]=="irreversible"
        for i in range(len(caps)-1)
    )


    rows.append(
        {
            "trace":trace,
            "length":len(caps),
            "hit":int(hit)
        }
    )


r=pd.DataFrame(rows)


X=sm.add_constant(
    r["length"]
)

y=r["hit"]


model=sm.Logit(
    y,
    X
).fit(
    disp=False
)


print(model.summary())


print()
print(
    "odds ratio"
)

print(
    model.params.apply(
        lambda x: __import__("numpy").exp(x)
    )
)
