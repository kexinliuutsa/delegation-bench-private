import json
def test_settings():
 d=json.load(open("settings.json")); assert d=={"limit":8,"mode":"stable"}
