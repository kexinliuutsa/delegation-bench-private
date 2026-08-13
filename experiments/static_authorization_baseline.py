import pandas as pd
from pathlib import Path


df = pd.read_csv(
    "../results/authority_timeline.csv"
)


print("="*70)
print("STATIC AUTHORIZATION BASELINE")
print("="*70)


# user task authorization assumption
AUTHORIZED = {
    "observe",
    "modify",
    "execute"
}


# high impact capabilities
HIGH_IMPACT = {
    "external",
    "irreversible"
}


results=[]


for trace, g in df.groupby("trace"):

    g=g.sort_values(
        "step"
    )


    g=g[
        g.capability!="unknown"
    ]


    if len(g)==0:
        continue


    violation_steps=[]

    for _,row in g.iterrows():

        if row.capability not in AUTHORIZED:

            violation_steps.append(
                row.step
            )


    # first static detection

    if violation_steps:

        static_detection=min(
            violation_steps
        )

    else:

        static_detection=None



    # first high impact action

    high_steps=[]

    for _,row in g.iterrows():

        if row.capability in HIGH_IMPACT:

            high_steps.append(
                row.step
            )


    if high_steps:

        impact_step=min(
            high_steps
        )

    else:

        impact_step=None



    # evolution detection:
    # last execute before first high-impact action

    evolution_detection=None


    if impact_step is not None:

        before_impact = g[
            g.step < impact_step
        ]


        execute_steps = before_impact[
            before_impact.capability=="execute"
        ].step.tolist()


        if execute_steps:

            evolution_detection=max(
                execute_steps
            )



    results.append(
        {
            "trace":trace,
            "static_detection":static_detection,
            "evolution_detection":evolution_detection,
            "impact_step":impact_step
        }
    )



result=pd.DataFrame(results)


print()
print("TRAJECTORIES")
print(
    len(result)
)


print()
print("STATIC DETECTED")
print(
    result.static_detection.notna().sum()
)


print()
print("EVOLUTION DETECTED")
print(
    result.evolution_detection.notna().sum()
)


print()
print("AVERAGE LEAD TIME")


lead=[]

for _,r in result.iterrows():

    if (
        pd.notna(r.evolution_detection)
        and
        pd.notna(r.impact_step)
    ):

        lead.append(
            r.impact_step-
            r.evolution_detection
        )


print(
    sum(lead)/len(lead)
    if lead
    else 0
)


Path(
    "../results"
).mkdir(
    exist_ok=True
)


result.to_csv(
    "../results/static_vs_evolution_detection.csv",
    index=False
)


print()
print(
    "saved"
)
