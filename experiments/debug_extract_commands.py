import json
import glob
import re


f = glob.glob(
    "../traces/public_swe_100/*swe-agent*.json"
)[0]


print("FILE:", f)


with open(f) as x:
    data=json.load(x)


for i,item in enumerate(data["trajectory"]):

    if item["role"] != "assistant":
        continue

    text=item.get("text")

    if not text:
        continue

    print("="*80)
    print("STEP", i)
    print(text[:1500])


