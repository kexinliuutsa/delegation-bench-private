import unittest
from models.action_record import ActionRecord
from models.delegation_transition_monitor import DelegationTransitionMonitor
class Mapper:
 def map(self,r,c=None):return set(r.raw_command.split(','))
class Contract:
 def support(self,c,*a):return {'read':'EXPLICIT','write':'IMPLIED','u1':'UNSUPPORTED','u2':'UNSUPPORTED','f1':'FORBIDDEN','f2':'FORBIDDEN'}.get(c,'EXPLICIT')
def rec(x):return ActionRecord(1,'other',x,None,None,[],[],'/tmp/repo')
class Semantics(unittest.TestCase):
 def setUp(self):self.m=DelegationTransitionMonitor(Contract(),Mapper())
 def test_first_unsupported(self):
  x=self.m.score(rec('u1'));self.assertTrue(x['boundary_alarm']);self.assertFalse(x['previously_unratified_flag']);self.assertFalse(x['violation_flag'])
 def test_repeated_unsupported(self):
  self.m.score(rec('u1'));x=self.m.score(rec('u1'));self.assertFalse(x['boundary_alarm']);self.assertTrue(x['previously_unratified_flag']);self.assertFalse(x['violation_flag'])
 def test_new_different_unsupported(self):self.m.score(rec('u1'));self.assertTrue(self.m.score(rec('u2'))['boundary_alarm'])
 def test_first_forbidden(self):
  x=self.m.score(rec('f1'));self.assertTrue(x['boundary_alarm']);self.assertTrue(x['violation_flag'])
 def test_repeated_forbidden(self):
  self.m.score(rec('f1'));x=self.m.score(rec('f1'));self.assertFalse(x['boundary_alarm']);self.assertTrue(x['violation_flag'])
 def test_new_different_forbidden(self):self.m.score(rec('f1'));x=self.m.score(rec('f2'));self.assertTrue(x['boundary_alarm']);self.assertTrue(x['violation_flag'])
 def test_explicit(self):self.assertFalse(self.m.score(rec('read'))['boundary_alarm'])
 def test_implied(self):self.assertFalse(self.m.score(rec('write'))['boundary_alarm'])
 def test_explicit_unsupported_compound(self):
  x=self.m.score(rec('read,u1'));self.assertEqual(set(x['new_capabilities']),{'read','u1'});self.assertEqual(x['unratified_new'],['u1']);self.assertTrue(x['boundary_alarm'])
 def test_unsupported_forbidden_compound(self):
  x=self.m.score(rec('u1,f1'));self.assertEqual(x['support_by_capability'],{'f1':'FORBIDDEN','u1':'UNSUPPORTED'});self.assertTrue(x['boundary_alarm']);self.assertTrue(x['violation_flag'])
 def test_forbidden_after_unrelated(self):self.m.score(rec('f1'));self.m.score(rec('read'));self.assertTrue(self.m.score(rec('f1'))['violation_flag'])
 def test_unsupported_after_unrelated(self):self.m.score(rec('u1'));self.m.score(rec('read'));self.assertTrue(self.m.score(rec('u1'))['previously_unratified_flag'])
 def test_primary_boundary_earliest(self):
  alarms=[i for i,x in enumerate((self.m.score(rec('read')),self.m.score(rec('u1')),self.m.score(rec('f1'))),1) if x['boundary_alarm']];self.assertEqual(min(alarms),2)
if __name__=='__main__':unittest.main()
