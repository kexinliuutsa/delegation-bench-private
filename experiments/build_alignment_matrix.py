import pandas as pd


cap=pd.read_csv(
    "../results/authority_timeline.csv"
)


dar=pd.read_csv(
    "../results/task_only_dar/expected_vs_observed_events.csv"
)


# remove unknown capability
cap=cap[
    cap.capability!="unknown"
]


print("="*70)
print("CAPABILITY DISTRIBUTION")
print("="*70)


print(
    cap.capability.value_counts()
)


print()


print("="*70)
print("DAR SUPPORT LEVEL")
print("="*70)


print(
    dar.task_support_level.value_counts()
)


# map capability to assumption
mapping={

    "observe":
        "Repository Inspection",

    "modify":
        "Repository Modification",

    "execute":
        "Code Execution",

    "external":
        "External Interaction",

    "irreversible":
        "Repository File Deletion"

}


rows=[]


for capability, assumption in mapping.items():

    subset=dar[
        dar.assumption==assumption
    ]


    if len(subset)==0:
        continue


    rows.append({

        "capability":
            capability,


        "assumption":
            assumption,


        "tasks":
            subset.trace.nunique(),


        "observed":
            subset.observed.sum(),


        "unsupported":
            subset.unsupported.sum(),


        "support_levels":
            ";".join(
                subset.task_support_level
                .unique()
            )

    })


result=pd.DataFrame(rows)


print()

print("="*70)
print("ALIGNMENT MATRIX")
print("="*70)


print(
    result.to_string(
        index=False
    )
)


result.to_csv(
    "../results/capability_assumption_alignment.csv",
    index=False
)


print()

print(
    "saved:",
    "../results/capability_assumption_alignment.csv"
)
