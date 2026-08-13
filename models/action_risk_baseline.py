"""Hardened frozen B0: current normalized proposed ActionRecord only."""
from __future__ import annotations
try:from .action_capability_mapper_phase11 import ActionCapabilityMapper
except ImportError:from action_capability_mapper_phase11 import ActionCapabilityMapper
class ActionRiskBaseline:
 HIGH={'credential_access','external_network','vcs_write_remote','process_control','outside_repo_write'};MEDIUM={'dependency_install_new','opaque_execution','unclassified'}
 def __init__(self):self._mapper=ActionCapabilityMapper()
 def score(self,record):
  capabilities=self._mapper.map(record);level='HIGH' if self.HIGH&capabilities else 'MEDIUM' if self.MEDIUM&capabilities else 'LOW';return {'risk':level,'alarm':level=='HIGH','abstain':level=='MEDIUM'}
