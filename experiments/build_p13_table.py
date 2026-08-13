import pandas as pd


alignment = pd.read_csv(
    "../results/capability_assumption_alignment.csv"
)


transition = pd.DataFrame(
    {
        "capability":[
            "observe",
            "modify",
            "execute",
            "external",
            "irreversible"
        ],

        "key_transition":[
            "observe->modify",
            "modify->irreversible",
            "execute->irreversible",
            "execute->external",
            "-"
        ],

        "transition_count":[
            75,
            17,
            43,
            9,
            0
        ]
    }
)


df = alignment.merge(
    transition,
    on="capability",
    how="left"
)


columns=[
    "capability",
    "assumption",
    "support_levels",
    "observed",
    "unsupported",
    "key_transition",
    "transition_count"
]


df=df[columns]


print("="*80)
print("P13 CAPABILITY-GROUNDING ALIGNMENT TABLE")
print("="*80)

print(
    df.to_string(
        index=False
    )
)


df.to_csv(
    "../results/P13_capability_grounding_alignment.csv",
    index=False
)


print()

print(
    "saved:",
    "../results/P13_capability_grounding_alignment.csv"
)
