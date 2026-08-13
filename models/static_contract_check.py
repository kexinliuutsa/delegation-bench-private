"""Frozen stateless B2 contract checker for replication v2.1."""
class StaticContractCheck:
 def __init__(self,contract,mapper):self.contract=contract;self.mapper=mapper
 def score(self,record,context=None):
  caps=sorted(self.mapper.map(record,context));support={c:self.contract.support(c,context) for c in caps};abstain=any(v in {'ABSTAIN','PENDING_UNRESOLVED'} for v in support.values());bad=sorted(c for c,v in support.items() if v in {'UNSUPPORTED','FORBIDDEN'})
  return {'capabilities':caps,'support_by_capability':support,'alarm':bool(bad) and not abstain,'unratified_current':bad,'abstain':abstain}
