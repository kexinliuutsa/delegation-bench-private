import json
import glob


f = glob.glob(
    "../traces/public_swe_100/*swe-agent*.json"
)[0]


with open(f) as x:
    data=json.load(x)


for i,item in enumerate(data["trajectory"]):

    if item["role"] == "ai":

        print("="*80)
        print("STEP:", i)

        print("TEXT TYPE:", type(item["text"]))

        print("TEXT:")
        print(
            item["text"][:2000]
        )

        break

