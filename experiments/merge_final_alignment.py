import pandas as pd


align=pd.read_csv(
    "../results/capability_assumption_alignment.csv"
)


data={

"observe":{
    "transition":"observe->modify"
},

"modify":{
    "transition":"modify->irreversible"
},

"execute":{
    "transition":"execute->irreversible"
},

"external":{
    "transition":"execute->external"
}

}


transition_counts={

"modify->irreversible":17,

"execute->irreversible":43,

"execute->external":9

}


for k,v in data.items():

    if k in align.capability.values:

        align.loc[
            align.capability==k,
            "key_transition"
        ]=v["transition"]


        align.loc[
            align.capability==k,
            "transition_count"
        ]=transition_counts.get(
            v["transition"],
            0
        )


print(
    align.to_string(index=False)
)


align.to_csv(
    "../results/final_alignment_matrix.csv",
    index=False
)
