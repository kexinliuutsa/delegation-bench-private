import json
import glob


f = glob.glob(
    "../traces/public_swe_100/*swe-agent*.json"
)[0]


print("FILE:", f)


with open(f) as x:
    data=json.load(x)


for i,item in enumerate(data["trajectory"]):

    if item["role"] == "assistant":

        print("="*80)
        print("STEP:", i)

        print("KEYS:")
        print(item.keys())

        for k,v in item.items():
            print()
            print("KEY:", k)
            print("TYPE:", type(v))
            print("VALUE:")
            print(str(v)[:500])

        break

