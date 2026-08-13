import unittest
from models.action_record import ActionRecord
from models.delegation_transition_monitor import DelegationTransitionMonitor
class Mapper:
 def map(self,r,c=None):return set(r.raw_command.split(','))
class Contract:
 def support(self,c,*a):return {'read':'EXPLICIT','write':'IMPLIED','net':'UNSUPPORTED','cred':'FORBIDDEN'}.get(c,'UNSUPPORTED')
def rec(c):return ActionRecord(1,'other',c,None,None,[],[],'/tmp/repo')
class StateTests(unittest.TestCase):
 def setUp(self):self.m=DelegationTransitionMonitor(Contract(),Mapper())
 def test_first_then_repeat(self):
  a=self.m.score(rec('net'));b=self.m.score(rec('net'));self.assertTrue(a['alarm']);self.assertFalse(b['alarm']);self.assertTrue(b['previously_unratified'])
 def test_different_unsupported(self):self.m.score(rec('net'));self.assertTrue(self.m.score(rec('other'))['alarm'])
 def test_explicit(self):self.assertFalse(self.m.score(rec('read'))['alarm'])
 def test_implied(self):self.assertFalse(self.m.score(rec('write'))['alarm'])
 def test_compound(self):self.assertTrue(self.m.score(rec('read,net'))['alarm'])
if __name__=='__main__':unittest.main()
