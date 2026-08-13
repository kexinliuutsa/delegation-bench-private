import pandas as pd


align=pd.read_csv(
    "../results/capability_assumption_alignment.csv"
)


trans=pd.read_csv(
    "../results/transition_matrix.csv"
)


important={

"execute":
[
("execute","irreversible"),
("execute","external")
],

"modify":
[
("modify","irreversible")
]

}


for c, pairs in important.items():

    count=0

    for a,b in pairs:

        x=trans[
            (trans["from"]==a)
            &
            (trans["to"]==b)
        ]

        if len(x):
            count+=x["count"].iloc[0]


    align.loc[
        align.capability==c,
        "high_impact_transitions"
    ]=count


print(
    align.to_string(index=False)
)


align.to_csv(
    "../results/alignment_with_transition.csv",
    index=False
)
