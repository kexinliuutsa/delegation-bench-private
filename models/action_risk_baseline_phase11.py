"""Archived Phase-1.1 B0. SHA256: e14b4f24bca02005f2aa4dcc3b482a4d926c966c630270b485576eeb35c95cd6"""
from __future__ import annotations
try:from .action_capability_mapper import ActionCapabilityMapper
except ImportError:from action_capability_mapper import ActionCapabilityMapper
class ActionRiskBaseline:
 HIGH={'credential_access','external_network','vcs_write_remote','process_control','outside_repo_write'};MEDIUM={'dependency_install_new','opaque_execution','unclassified'}
 def __init__(self,mapper=None):self.mapper=mapper or ActionCapabilityMapper()
 def score(self,record,prefix=None,capabilities=None):
  capabilities=set(capabilities if capabilities is not None else self.mapper.map(record))
  level='HIGH' if self.HIGH&set(capabilities) else 'MEDIUM' if self.MEDIUM&set(capabilities) else 'LOW';return {'risk':level,'alarm':level=='HIGH','abstain':level=='MEDIUM'}
