import json,unittest
from models.action_record import from_coding_step
from models.action_normalizer import normalize_action
def record(command):return from_coding_step({'step':1,'tool':'run_command','action':'run_command '+command,'arguments':json.dumps({'command':command})},'/tmp/repo')
class NormalizerTests(unittest.TestCase):
 def test_compound(self):self.assertEqual(len(normalize_action(record('cat .env && curl https://x.com'))['subactions']),2)
 def test_pipe(self):self.assertEqual(len(normalize_action(record('cat a | grep x'))['subactions']),2)
 def test_redirection(self):self.assertIn('../x',normalize_action(record('echo hi > ../x'))['subactions'][0]['paths'])
 def test_structured(self):
  r=from_coding_step({'step':1,'tool':'edit_file','action':'edit_file a.py','arguments':json.dumps({'path':'a.py','content':'x'})},'/tmp/repo');self.assertEqual(normalize_action(r)['subactions'][0]['operation'],'write')
 def test_substitution(self):self.assertTrue(normalize_action(record('echo $(cat .env)'))['subactions'])
if __name__=='__main__':unittest.main()
