import json
def test_value(): assert json.load(open('app_config.json'))['port'] == 8080
