import json
import glob
from collections import Counter


f = glob.glob(
    "../traces/public_swe_100/*swe-agent*.json"
)[0]


with open(f) as x:
    data=json.load(x)


print("FILE:", f)

roles = [
    x.get("role")
    for x in data["trajectory"]
]

print()
print("ROLE COUNTS:")
print(
    Counter(roles)
)


print()
print("ALL ROLES:")
for i,item in enumerate(data["trajectory"]):
    print(
        i,
        item.get("role"),
        item.keys()
    )

