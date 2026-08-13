import pandas as pd
import json
from pathlib import Path


df=pd.read_csv(
    "results/authority_timeline.csv"
)


config={

    "rows":len(df),

    "traces":df.trace.nunique(),

    "capability_counts":
        df.capability.value_counts()
        .to_dict(),

    "unknown_rows":
        int(
            (df.capability=="unknown").sum()
        ),

    "filtered_unknown":
        True,

    "permutation_runs":
        1000,

    "transition_definition":
        "adjacent steps only, gap >= 1"

}


Path(
    "results/experiment_config.json"
).write_text(
    json.dumps(
        config,
        indent=2
    )
)


print(
    json.dumps(
        config,
        indent=2
    )
)
