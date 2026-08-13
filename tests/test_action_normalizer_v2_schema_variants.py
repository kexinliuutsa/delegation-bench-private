import unittest
from models.action_normalizer_v2 import normalize_action,canonicalize_fields
class TestSchemaVariants(unittest.TestCase):
 def eq(self,a,b):self.assertEqual(normalize_action(a)['subactions'],normalize_action(b)['subactions'])
 def test_read(self):self.eq({'tool_name':'read_file','tool_args':{'path':'README.md'}},{'tool_name':'read_file','path':'README.md'})
 def test_edit(self):self.eq({'tool_name':'edit_file','tool_args':{'path':'a.py'}},{'tool_name':'edit_file','filename':'a.py'})
 def test_command(self):
  self.eq({'tool_name':'run_command','tool_args':{'command':'pytest -q'}},{'tool_name':'run_command','cmd':'pytest -q'})
 def test_search(self):self.eq({'tool_name':'search_text','tool_args':{'path':'src','query':'x'}},{'tool_name':'search_text','path':'src','query':'x'})
 def test_missing(self):self.assertEqual(canonicalize_fields({'tool_name':'read_file'})['status'],'ABSTAIN')
 def test_conflict(self):self.assertEqual(canonicalize_fields({'tool_name':'read_file','path':'a','tool_args':{'path':'b'}})['status'],'ABSTAIN')
 def test_unknown(self):self.assertEqual(canonicalize_fields({'tool_name':'mystery','path':'a'})['status'],'ABSTAIN')
if __name__=='__main__':unittest.main()
