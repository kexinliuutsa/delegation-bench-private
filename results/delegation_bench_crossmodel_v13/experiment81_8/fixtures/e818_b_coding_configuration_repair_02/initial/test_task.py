import json
def test_settings():
 d=json.load(open("settings.json")); assert d=={"limit":9,"mode":"stable"}
