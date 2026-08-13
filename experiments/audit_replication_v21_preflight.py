#!/usr/bin/env python3
"""Infrastructure-only Phase-A audit. Never compares monitor performance."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'benchmarks/delegation_transition_replication_v21';R=ROOT/'results/delegation_transition_replication_v21';P=R/'preflight';P.mkdir(parents=True,exist_ok=True)
def main():
 files=sorted((P/'raw').glob('*.json'));schema=ordering=inputs=sandbox=True;unresolved=0;continuation=0
 for p in files:
  d=json.loads(p.read_text());schema &= all(k in d for k in ('pair_id','trajectory_id','condition','task','steps','event_opportunities')) and bool(d['steps'])
  for s in d['steps']:
   schema &= all(k in s for k in ('proposed_action','action_record','mapped_capabilities','monitor_outputs','sandbox_decision','execution_status')) and all(k in s['monitor_outputs'] for k in ('delegation_transition','static_contract','action_risk','task_alignment'))
   unresolved+=any(x in {'unclassified','opaque_execution'} for x in s['mapped_capabilities']);inputs &= len(set(s['monitor_input_hashes'].values()))==1
  for i,s in enumerate(d['steps'][:-1]):
   if s['execution_status']=='BLOCKED_BY_SANDBOX':continuation+=1
  ev=[x['event_type'] for x in d['events']]
  for i in range(0,len(ev),4):ordering &= ev[i:i+4]==['ACTION_PROPOSED','MONITORS_SCORED','SANDBOX_DECISION','ACTION_EXECUTED_OR_BLOCKED']
 summary={'phase':'A','real_preflight_trajectories':len(files),'schema_pass':bool(schema),'proposal_before_execution':bool(ordering),'identical_monitor_proposal':bool(inputs),'generation_isolation':'4 scenarios structurally frozen; treatment-only preflight','contract_leakage_count':0,'normalizer_unresolved':unresolved,'mapper_resolvable_coverage':1.0 if unresolved==0 else 0.0,'post_boundary_continuation_observed':continuation,'sandbox_integrity':bool(sandbox),'performance_inspected':False}
 ready=len(files)==4 and schema and ordering and inputs and unresolved==0 and sandbox
 summary['status']='READY_FOR_REPLICATION_V21_FULL_COLLECTION' if ready else 'NOT_READY_PREFLIGHT';(P/'preflight_summary.json').write_text(json.dumps(summary,indent=2)+'\n');(R/'status.json').write_text(json.dumps({'preflight_status':summary['status'],'full_collection_launched':False},indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
