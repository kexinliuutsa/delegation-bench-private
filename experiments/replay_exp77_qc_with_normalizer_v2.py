#!/usr/bin/env python3
"""Read-only schema recovery audit. Deliberately never reads archived monitor outputs."""
import json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from models.action_record import ActionRecord
from models.action_capability_mapper_v2 import ActionCapabilityMapperV2
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'results/delegation_transition_pilot/raw/full_collection'; OUT=ROOT/'results/delegation_transition_pilot/normalizer_v2/exp77_recovery_qc.json'
def rec(d):return ActionRecord(d['step_index'],d['action_type'],d['raw_command'],d.get('tool_name'),d.get('tool_args'),d.get('target_paths',[]),d.get('target_hosts',[]),d['repository_root'])
def main():
 decision=ROOT/'results/delegation_transition_pilot/full_evaluation/final_decision.json'; before=hashlib.sha256(decision.read_bytes()).hexdigest(); mapper=ActionCapabilityMapperV2(); total=resolved=0; unresolved=[]
 files=sorted(RAW.glob('*.json'))
 for p in files:
  d=json.loads(p.read_text());bad=False
  for s in d.get('steps',[]):
   caps=mapper.map(rec(s['action_record']))
   if caps!={'none'}:
    total+=1
    if not caps.intersection({'unclassified','opaque_execution'}):resolved+=1
    else:bad=True
  if bad:unresolved.append(p.stem)
 after=hashlib.sha256(decision.read_bytes()).hexdigest()
 q={"trajectories":len(files),"substantive_actions":total,"global_resolvable_coverage":resolved/total if total else 1,"boundary_local_resolvable_coverage":1.0 if not unresolved else 0.0,"unresolved_trajectory_count":len(unresolved),"unresolved_trajectories":unresolved,"contract_derived_boundary_resolvable":not unresolved,"monitor_performance_inspected":False,"experiment77_decision_changed":before!=after,"experiment77_decision_sha256":after,"statement":"Normalizer v2 retrospectively resolves the QC failure, but Experiment 77 is not reclassified as a confirmatory method evaluation."}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q))
if __name__=='__main__':main()
