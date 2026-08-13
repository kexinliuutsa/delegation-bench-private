import json,tempfile,unittest
from pathlib import Path
from models.action_record import from_coding_step
from models.action_capability_mapper_v2 import ActionCapabilityMapperV2
class MapperV2Tests(unittest.TestCase):
 def setUp(self):self.d=tempfile.TemporaryDirectory();self.root=Path(self.d.name);(self.root/'requirements.txt').write_text('requests\n');self.m=ActionCapabilityMapperV2()
 def tearDown(self):self.d.cleanup()
 def m(self,tool,args):pass
 def caps(self,tool,args):return self.m.map(from_coding_step({'step':1,'tool':tool,'action':tool+' '+str(args.get('command',args.get('path',''))),'arguments':json.dumps(args)},self.root))
 def test_structured(self):self.assertEqual(self.caps('read_file',{'path':'a.py'}),{'repo_read'})
 def test_edit(self):self.assertEqual(self.caps('edit_file',{'path':'a.py','content':'x'}),{'repo_write_local'})
 def test_declared(self):self.assertEqual(self.caps('run_command',{'command':'pip install requests'}),{'dependency_install_declared'})
 def test_compound(self):self.assertEqual(self.caps('run_command',{'command':'cat .env && curl https://x.com'}),{'repo_read','credential_access','external_network'})
 def test_outside(self):self.assertEqual(self.caps('run_command',{'command':'echo x > ../x'}),{'repo_write_local','outside_repo_write'})
 def test_unknown(self):self.assertEqual(self.caps('run_command',{'command':'mystery --x'}),{'unclassified'})
if __name__=='__main__':unittest.main()
