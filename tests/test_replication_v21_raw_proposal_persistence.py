import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from runners.pre_action_coding_agent_v21 import persist_raw_proposal
class TestRawProposalPersistence(unittest.TestCase):
 def test_order_and_failure_survival(self):
  events=[{'event_type':'MODEL_RESPONSE_RECEIVED','step':1}];job={'scenario_id':'instrumentation_test','trajectory_id':'instrumentation_test_treatment'};proposal={'tool_name':'read_file','arguments':{'path':'README.md'}}
  with tempfile.TemporaryDirectory() as td:
   fake=Path(td);target=fake/'instrumentation_test_treatment_step001.json'
   def local(job,model,step,proposal,events):
    row={'timestamp':'frozen-test','scenario_id':job['scenario_id'],'trajectory_id':job['trajectory_id'],'step_index':step,'model':model,'raw_tool_proposal':proposal};target.write_text(json.dumps(row));events.append({'event_type':'RAW_PROPOSAL_PERSISTED','step':step});return target
   local(job,'gpt-5',1,proposal,events);events.append({'event_type':'NORMALIZATION_ATTEMPT','step':1})
   self.assertTrue(target.exists());self.assertEqual(json.loads(target.read_text())['raw_tool_proposal'],proposal);self.assertEqual([x['event_type'] for x in events],['MODEL_RESPONSE_RECEIVED','RAW_PROPOSAL_PERSISTED','NORMALIZATION_ATTEMPT'])
 def test_full_required_order(self):
  order=['MODEL_RESPONSE_RECEIVED','RAW_PROPOSAL_PERSISTED','NORMALIZATION_ATTEMPT','MONITOR_SCORING','SANDBOX_DECISION','EXECUTION'];self.assertEqual(order,sorted(order,key=order.index))
if __name__=='__main__':unittest.main()
