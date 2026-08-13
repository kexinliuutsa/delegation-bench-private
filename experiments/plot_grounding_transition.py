import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


df = pd.read_csv(
    "../results/P13_capability_grounding_alignment.csv"
)


order=[
    "observe",
    "modify",
    "execute",
    "external",
    "irreversible"
]


df["capability"] = pd.Categorical(
    df["capability"],
    categories=order,
    ordered=True
)


df=df.sort_values(
    "capability"
)


# convert grounding

grounding_map={
    "strongly_implied":3,
    "strongly_implied;explicit":3,
    "weakly_implied":2,
    "unsupported":1
}


df["grounding_score"] = (
    df.support_levels
    .map(grounding_map)
)


x=np.arange(
    len(df)
)


fig,ax1=plt.subplots(
    figsize=(8,4)
)


ax1.bar(
    x,
    df.grounding_score
)


ax1.set_ylabel(
    "Task Grounding Level\n(3=Strong,2=Weak,1=Unsupported)"
)


ax1.set_xticks(
    x
)

ax1.set_xticklabels(
    df.capability,
    rotation=30
)


ax2=ax1.twinx()


ax2.plot(
    x,
    df.transition_count,
    marker="o"
)


ax2.set_ylabel(
    "High-impact Transition Count"
)


plt.tight_layout()


plt.savefig(
    "../results/figure3_grounding_transition.png",
    dpi=300
)


print(
    "saved figure3"
)
