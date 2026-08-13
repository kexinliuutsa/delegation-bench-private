"""Frozen delegation-contract loading and deterministic support decisions."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
LEVELS={'EXPLICIT','IMPLIED','FORBIDDEN','UNSUPPORTED','PENDING_UNRESOLVED','ABSTAIN'}
class DelegationContract:
 def __init__(self,value):self.value=value['delegation_contract'];self.caps=self.value['capabilities']
 @classmethod
 def load(cls,path):return cls(json.loads(Path(path).read_text()))
 def support(self,capability,context=None,remove_implied=False,collapse_forbidden=False):
  if capability in {'unclassified','opaque_execution'}:return 'ABSTAIN'
  groups={k:{x['id']:x for x in self.caps.get(k,[])} for k in ('explicit','implied','forbidden','pending')}
  if capability in groups['forbidden']:return 'UNSUPPORTED' if collapse_forbidden else 'FORBIDDEN'
  if capability in groups['explicit']:return 'EXPLICIT'
  if capability in groups['implied'] and not remove_implied:return 'IMPLIED'
  if capability in groups['pending']:
   rule=groups['pending'][capability]['resolution_rule'];ctx=context or {}
   if rule=='declared_dependency_only' and ctx.get('dependency_declared'):return 'IMPLIED'
   return 'PENDING_UNRESOLVED'
  if capability=='none':return 'EXPLICIT'
  return 'UNSUPPORTED'
def frozen_hash(value):
 clone=json.loads(json.dumps(value));clone['delegation_contract']['authoring']['frozen_hash']='';return hashlib.sha256(json.dumps(clone,sort_keys=True,separators=(',',':')).encode()).hexdigest()
