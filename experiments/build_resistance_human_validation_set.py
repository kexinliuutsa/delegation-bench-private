#!/usr/bin/env python3
"""Build the frozen, blind Experiment-82A.2 human validation package."""
from __future__ import annotations
import csv, hashlib, json, random
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BENCH=ROOT/'benchmarks/delegation_bench_v1'; RAW=ROOT/'results/delegation_bench_v1/raw'
OUT=BENCH/'resistance'; RES=ROOT/'results/delegation_bench_v1/resistance_judge_validation'
SEED=82120; TARGET=120
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def safe_json(x):
 try:return json.loads(x) if isinstance(x,str) else (x or {})
 except Exception:return {'raw':x}
def text(v): return v if isinstance(v,str) else canon(v)

def packet(step, prior):
 args=safe_json(step.get('arguments'))
 tool=step.get('tool',''); agent=step.get('action') or args.get('summary') or args.get('message') or ''
 prefix=[]
 for s in prior[-3:]:
  prefix.append({'step':s.get('step'),'action':s.get('action') or s.get('tool'),'observation':text(safe_json(s.get('observation')))[:500]})
 current_obs=text(safe_json(prior[-1].get('observation')))[:1000] if prior else ''
 return {'observable_prefix':prefix,'current_observation':current_obs,'current_agent_text':agent,
         'current_proposed_action_or_tool_call':{'tool':tool,'arguments':args},'current_step_index':step.get('step')}

def main():
 OUT.mkdir(parents=True,exist_ok=True);RES.mkdir(parents=True,exist_ok=True)
 target=OUT/'human_validation_sample.json'
 if target.exists(): raise SystemExit('human validation sample already frozen')
 m=json.loads((BENCH/'collection_manifest.json').read_text()); jobs=m['jobs']; pairmeta={p['pair_id']:p for p in m['pairs']}
 # Treatment actual exposure is the matched boundary for both conditions.
 exposures={}
 for p in pairmeta:
  fp=RAW/f'{p}_treatment.json'
  if fp.exists(): exposures[p]=json.loads(fp.read_text()).get('actual_exposure_step')
 candidates=[]
 for j in jobs:
  fp=RAW/f"{j['pair_id']}_{j['condition']}.json"
  if not fp.exists(): continue
  d=json.loads(fp.read_text()); steps=d.get('steps',[]); exp=exposures.get(j['pair_id'])
  if not isinstance(exp,int): continue
  for i,s in enumerate(steps):
   n=int(s.get('step',i+1))
   temporal='pre-exposure' if n<=exp else ('first post-exposure response' if n==exp+1 else 'later post-exposure')
   # retain all three positions; sampling, never keywords or outcomes, determines inclusion
   candidates.append({'trajectory_id':j['trajectory_id'],'pair_id':j['pair_id'],
    '_condition':j['condition'],'_paradigm':j['paradigm'],'_style':j['intervention_style'],
    '_family':j['task_family'],'_temporal':temporal,'task_text':j['task'],**packet(s,steps[:i])})
 # Round-robin over condition/paradigm/style/temporal, with deterministic within-stratum order.
 rng=random.Random(SEED); groups=defaultdict(list)
 for x in candidates: groups[(x['_condition'],x['_paradigm'],x['_style'],x['_temporal'])].append(x)
 for xs in groups.values(): rng.shuffle(xs)
 selected=[]
 while len(selected)<min(TARGET,len(candidates)) and any(groups.values()):
  for key in sorted(groups):
   if groups[key] and len(selected)<TARGET: selected.append(groups[key].pop())
 if len(selected)<80: raise SystemExit(f'insufficient real decision points: {len(selected)}')
 blind=[]; dist=[]
 for i,x in enumerate(selected,1):
  sid=f'R82A2_{i:03d}'
  blind.append({'sample_id':sid,'task_text':x['task_text'],'observable_prefix':x['observable_prefix'],
   'current_observation':x['current_observation'],'current_agent_text':x['current_agent_text'],
   'current_proposed_action_or_tool_call':x['current_proposed_action_or_tool_call'],'current_step_index':x['current_step_index']})
  dist.append({'sample_id':sid,'condition':x['_condition'],'paradigm':x['_paradigm'],'intervention_style':x['_style'],
               'temporal_position':x['_temporal'],'task_family':x['_family']})
 payload={'experiment':'82A.2','status':'FROZEN_BEFORE_ANNOTATION','random_seed':SEED,
  'sampling_firewall':['no PIDR values','no divergence values','no refusal keywords','no rule predictions','no monitor outcomes'],
  'n':len(blind),'examples':blind}
 payload['examples_sha256']=sha_bytes(canon(blind).encode());target.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
 fields=['sample_id','task_text','observable_prefix','current_observation','current_agent_text','current_proposed_action_or_tool_call','current_step_index','label','confidence','evidence_span','annotator_note']
 for name,seed in [('A',82121),('B',82122)]:
  rows=list(blind);random.Random(seed).shuffle(rows)
  with (OUT/f'annotation_packet_{name}.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for x in rows:w.writerow({**x,'observable_prefix':canon(x['observable_prefix']),'current_proposed_action_or_tool_call':canon(x['current_proposed_action_or_tool_call']),'label':'','confidence':'','evidence_span':'','annotator_note':''})
 # Aggregate-only distribution avoids exposing hidden design variables to annotators.
 rows=[]
 for dim in ('condition','paradigm','intervention_style','temporal_position','task_family'):
  for level,n in sorted(Counter(x[dim] for x in dist).items()):rows.append({'dimension':dim,'level':level,'N':n})
 with (RES/'sample_distribution.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['dimension','level','N']);w.writeheader();w.writerows(rows)
 print(json.dumps({'N':len(blind),'sample_sha256':payload['examples_sha256'],'distribution':rows},indent=2))
if __name__=='__main__':main()
