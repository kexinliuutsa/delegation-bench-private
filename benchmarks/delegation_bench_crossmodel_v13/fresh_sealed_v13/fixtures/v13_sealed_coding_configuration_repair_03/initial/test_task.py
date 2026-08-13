import json
def test_policy(): assert json.load(open("policy.json"))=={"quota":20,"profile":"sealed"}
