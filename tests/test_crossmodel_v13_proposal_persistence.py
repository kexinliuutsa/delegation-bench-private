import json,tempfile,unittest
from pathlib import Path
from runners.crossmodel_v13_agent import persist_proposal,event
class TestPersistence(unittest.TestCase):
 def test_order_and_survival(self):
  with tempfile.TemporaryDirectory() as d:
   raw=Path(d)/'raw.jsonl';ev=Path(d)/'events.jsonl';ctx={'model':'m','pair_id':'p','trajectory_id':'t','condition':'c'}
   event(ev,'MODEL_PROPOSAL_RECEIVED',1,**ctx,step=1);persist_proposal(raw,ctx,1,{'tool':'read_file','path':'missing'});event(ev,'RAW_PROPOSAL_PERSISTED',2,**ctx,step=1);event(ev,'NORMALIZATION',3,**ctx,step=1);event(ev,'DISPATCH_CLASSIFICATION',4,**ctx,step=1);event(ev,'EXECUTOR_SELECTION',5,**ctx,step=1);event(ev,'FILESYSTEM/TOOL_EXECUTION',6,**ctx,step=1)
   self.assertTrue(raw.exists());self.assertEqual([json.loads(x)['sequence'] for x in ev.read_text().splitlines()],[1,2,3,4,5,6]);self.assertEqual(json.loads(raw.read_text())['raw_structured_proposal']['path'],'missing')
if __name__=='__main__':unittest.main()
