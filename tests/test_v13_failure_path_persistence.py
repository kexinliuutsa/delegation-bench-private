import json,tempfile,unittest
from pathlib import Path
from runners.crossmodel_v13_agent import persist_proposal
from runners.crossmodel_v13_failure_qc import assert_failed_job_has_raw_proposal,MissingRawProposalForFailedJob

class SyntheticDispatchFailure(RuntimeError):pass
class FailurePathPersistenceTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ctx={'model':'offline','pair_id':'p','trajectory_id':'t','condition':'diagnostic'}
 def tearDown(self):self.tmp.cleanup()
 def persist_then_fail(self,proposal,step=1):
  path=self.root/'raw.jsonl';ctx={**self.ctx,'record_id':f'r{step}','protocol_version':'v1.3-81.7b','fixture_id':'fixture','step_index':step,'persistence_timestamp':'test','downstream_status':'EXPECTED_FAILURE','exception_type':'SyntheticDispatchFailure','exception_message':'forced post-persistence failure'};persist_proposal(path,ctx,step,proposal);row={'record_id':ctx['record_id']}
  try:raise SyntheticDispatchFailure('forced post-persistence failure')
  except SyntheticDispatchFailure:pass
  return path,row
 def test_valid_read_then_executor_failure(self):
  p,_=self.persist_then_fail({'tool':'read_file','path':'README.md'});self.assertEqual(json.loads(p.read_text())['raw_tool_name'],'read_file')
 def test_valid_action_then_dispatch_failure(self):self.assertTrue(self.persist_then_fail({'tool':'list_files','path':'.'})[0].exists())
 def test_invalid_schema_persisted(self):self.assertEqual(json.loads(self.persist_then_fail({'path':'x'})[0].read_text())['raw_structured_proposal'],{'path':'x'})
 def test_unknown_tool_persisted(self):self.assertEqual(json.loads(self.persist_then_fail({'tool':'unknown','path':'x'})[0].read_text())['raw_tool_name'],'unknown')
 def test_record_survives_exception(self):self.assertGreater(self.persist_then_fail({'tool':'read_file','path':'x'})[0].stat().st_size,0)
 def test_append_only_prior_record_unchanged(self):
  path,row1=self.persist_then_fail({'tool':'read_file','path':'a'},1);first=path.read_bytes();ctx={**self.ctx,'record_id':'r2','protocol_version':'v1.3-81.7b','fixture_id':'fixture','step_index':2,'persistence_timestamp':'test','downstream_status':'EXPECTED_FAILURE','exception_type':'SyntheticDispatchFailure','exception_message':'forced post-persistence failure'};persist_proposal(path,ctx,2,{'tool':'read_file','path':'b'});row2={'record_id':'r2'};self.assertTrue(path.read_bytes().startswith(first));self.assertNotEqual(row1['record_id'],row2['record_id'])
 def test_post_proposal_missing_raw_fails_qc(self):
  with self.assertRaisesRegex(MissingRawProposalForFailedJob,'MISSING_RAW_PROPOSAL_FOR_FAILED_JOB'):assert_failed_job_has_raw_proposal('t',self.root/'none',True,'POST_PROPOSAL_FAILURE')
 def test_pre_proposal_transport_failure_exempt(self):self.assertTrue(assert_failed_job_has_raw_proposal('t',self.root/'none',False,'PRE_PROPOSAL_FAILURE'))
 def test_same_trajectory_distinct_steps_and_ids(self):
  path=self.root/'many.jsonl';a={'record_id':'r1',**self.ctx,'protocol_version':'v1.3-81.7b','fixture_id':'f','step_index':1,'persistence_timestamp':'t','downstream_status':'PENDING','exception_type':None,'exception_message':None};b={**a,'record_id':'r2','step_index':2};persist_proposal(path,a,1,{'tool':'read_file','path':'a'});persist_proposal(path,b,2,{'tool':'read_file','path':'b'});rows=[json.loads(x) for x in path.read_text().splitlines()];self.assertEqual([x['step_index'] for x in rows],[1,2]);self.assertNotEqual(a['record_id'],b['record_id'])
 def test_structured_content_matches_input(self):
  proposal={'tool':'read_file','path':'README.md','notice':'unrelated'};p,_=self.persist_then_fail(proposal);self.assertEqual(json.loads(p.read_text())['raw_structured_proposal'],proposal)
 def test_required_record_fields(self):
  p,_=self.persist_then_fail({'tool':'read_file','path':'x'});row=json.loads(p.read_text());required={'record_id','timestamp','protocol_version','fixture_id','trajectory_id','step_index','raw_tool_name','raw_tool_arguments','raw_structured_proposal','persistence_timestamp','downstream_status','exception_type','exception_message'};self.assertTrue(required<=row.keys())
if __name__=='__main__':unittest.main()
