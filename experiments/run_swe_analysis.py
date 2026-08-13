
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))


sys.path.append(
    str(
        Path(__file__)
        .resolve()
        .parents[1]
    )
)


from data_adapters.swe.extract import load_swe_trace
from framework.trajectory import build_timeline, summarize
from framework.analyzer import (
    capability_timeline,
    detect_escalation
)


TRACE_DIR = Path(
    "../traces/public_swe_100"
)


if __name__ == "__main__":


    files=list(
        TRACE_DIR.glob("*.json")
    )


    print(
        "traces:",
        len(files)
    )


    trace=load_swe_trace(
        files[0]
    )


    print(
        "\nTRACE:",
        trace["trace"]
    )


    events=build_timeline(
        trace["actions"]
    )


    print(
        "\nAUTHORITY TIMELINE"
    )


    for x in capability_timeline(events):

        print(x)



    print(
        "\nESCALATION EVENTS"
    )


    for e in detect_escalation(events):

        print(e)
