import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import pandas as pd

from data_adapters.swe.extract import load_swe_trace
from framework.trajectory import build_timeline
from framework.analyzer import (
    capability_timeline,
    detect_escalation
)


TRACE_DIR = Path("../traces/public_swe_100")
OUT_DIR = Path("../results")

OUT_DIR.mkdir(exist_ok=True)


timeline_rows=[]
escalation_rows=[]
summary_rows=[]
transition_rows=[]


files=list(
    TRACE_DIR.glob("*.json")
)


print("traces:",len(files))


for path in files:

    trace=load_swe_trace(path)

    events=build_timeline(
        trace["actions"]
    )

    timeline=capability_timeline(events)

    escalations=detect_escalation(events)


    levels=[
        {
            "observe":1,
            "modify":2,
            "execute":3,
            "external":4,
            "irreversible":5
        }.get(
            x["capability"],
            0
        )
        for x in timeline
    ]


    for i,x in enumerate(timeline):

        timeline_rows.append(
            {
                "trace":trace["trace"],
                "step":x["step"],
                "action":x["action"],
                "capability":x["capability"],
                "level":levels[i]
            }
        )


    for e in escalations:

        escalation_rows.append(
            {
                "trace":trace["trace"],
                **e
            }
        )


    for a,b in zip(
        timeline[:-1],
        timeline[1:]
    ):

        transition_rows.append(
            {
                "from":a["capability"],
                "to":b["capability"]
            }
        )


    summary_rows.append(
        {
            "trace":trace["trace"],
            "steps":len(events),
            "num_escalations":len(escalations),
            "max_level":max(levels) if levels else 0,
            "irreversible":
                int(5 in levels)
        }
    )


pd.DataFrame(
    timeline_rows
).to_csv(
    OUT_DIR/"authority_timeline.csv",
    index=False
)


pd.DataFrame(
    escalation_rows
).to_csv(
    OUT_DIR/"escalation_events.csv",
    index=False
)


pd.DataFrame(
    summary_rows
).to_csv(
    OUT_DIR/"trajectory_summary.csv",
    index=False
)


pd.DataFrame(
    transition_rows
).value_counts(
    ["from","to"]
).reset_index(
    name="count"
).to_csv(
    OUT_DIR/"transition_matrix.csv",
    index=False
)


print("done")
