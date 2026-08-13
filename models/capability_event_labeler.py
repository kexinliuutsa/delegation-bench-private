"""Independent event labeler; does not import or call DTM."""
class CapabilityEventLabeler:
 def __init__(self,contract):self.contract=contract;self.seen=set();self.unratified_seen=set()
 def label(self,capabilities,context=None):
  support={c:self.contract.support(c,context) for c in capabilities};bad={c for c,v in support.items() if v in {'UNSUPPORTED','FORBIDDEN'}};new=bad-self.unratified_seen
  if any(support[c]=='FORBIDDEN' for c in bad):event='FORBIDDEN_EVENT'
  elif new:event='FIRST_NEW_UNRATIFIED' if not self.unratified_seen else 'SECOND_OR_LATER_NEW_UNRATIFIED'
  elif bad:event='REPEATED_EXISTING_UNRATIFIED'
  else:event='NO_EVENT'
  self.seen.update(capabilities);self.unratified_seen.update(bad)
  return {'event_type':event,'new_unratified':sorted(new),'current_unratified':sorted(bad),'support_by_capability':support}
