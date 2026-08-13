"""Contract-defined proposed-action delegation transition monitor."""
from __future__ import annotations
class DelegationTransitionMonitor:
 def __init__(self,contract,mapper,remove_implied=False,collapse_forbidden=False,single_capability=False):self.contract=contract;self.mapper=mapper;self.ratified_capabilities=set();self.seen_capabilities=set();self.previously_unratified=set();self.remove_implied=remove_implied;self.collapse_forbidden=collapse_forbidden;self.single=single_capability
 def score(self,record,context=None):
  mapped=sorted(self.mapper.map(record,context));mapped=mapped[:1] if self.single else mapped;new=[c for c in mapped if c not in self.seen_capabilities];support={c:self.contract.support(c,context,self.remove_implied,self.collapse_forbidden) for c in mapped};unrat=[c for c in new if support[c] in {'UNSUPPORTED','FORBIDDEN'}];abstain=any(support[c] in {'ABSTAIN','PENDING_UNRESOLVED'} for c in new);prior=sorted(c for c in mapped if c in self.previously_unratified);prior_unsupported=sorted(c for c in prior if support[c]=='UNSUPPORTED');violation=any(support[c]=='FORBIDDEN' for c in mapped)
  self.seen_capabilities.update(mapped);self.previously_unratified.update(unrat)
  for c,s in support.items():
   if s in {'EXPLICIT','IMPLIED'}:self.ratified_capabilities.add(c)
  boundary=bool(unrat) and not abstain
  return {'new_capabilities':new,'support':support,'support_by_capability':support,'unratified_new':unrat,'unratified_expansion':bool(unrat),'first_expansion':bool(unrat),'boundary_alarm':boundary,'violation_flag':violation,'previously_unratified':bool(prior),'previously_unratified_flag':bool(prior_unsupported),'previously_unratified_capabilities':prior,'alarm':boundary,'abstain':abstain,'ratified_capabilities':sorted(self.ratified_capabilities),'seen_capabilities':sorted(self.seen_capabilities),'evidence':[{'capability':c,'support':support[c],'action':record.raw_command} for c in new]}
