import json
def test_policy(): assert json.load(open("policy.json"))=={"quota":21,"profile":"sealed"}
