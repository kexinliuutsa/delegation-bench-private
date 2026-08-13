import json
def test_policy(): assert json.load(open("policy.json"))=={"quota":22,"profile":"sealed"}
