#!/usr/bin/env python3
"""Behavioral-equivalence and semantic audits; no performance evaluation."""
from __future__ import annotations
import csv,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));OUT=ROOT/'results/delegation_transition_pilot/phase11b';RAW=ROOT/'results/delegation_transition_pilot/phase11/diagnostic_rollouts'
from action_record import ActionRecord
from action_capability_mapper_phase11 import ActionCapabilityMapper
from action_risk_baseline import ActionRiskBaseline as NewRisk
from action_risk_baseline_phase11 import ActionRiskBaseline as OldRisk
from task_alignment_baseline import TaskAlignmentBaseline as NewAlign
from task_alignment_baseline_phase11 import TaskAlignmentBaseline as OldAlign
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True);oldm=ActionCapabilityMapper();oldr=OldRisk();newr=NewRisk();olda=OldAlign();newa=NewAlign();rows=[]
 for p in sorted(RAW.glob('*.json')):
  t=json.loads(p.read_text());prefix=[]
  for s in t['steps']:
   r=ActionRecord(**s['action_record']);caps=oldm.map(r);a=oldr.score(r,prefix,capabilities=caps);b=newr.score(r);c=olda.score(t['task'],r,caps,{'prefix':prefix});d=newa.score(t['task'],prefix,r);rows.append({'trajectory_id':t['trajectory_id'],'step_index':s['step_index'],'b0_old':json.dumps(a,sort_keys=True),'b0_new':json.dumps(b,sort_keys=True),'b0_equal':a==b,'b1_old':json.dumps(c,sort_keys=True),'b1_new':json.dumps(d,sort_keys=True),'b1_equal':c==d});prefix.append({'proposal':s['proposed_action'],'observation':s['observation']})
 with (OUT/'baseline_behavior_equivalence.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 budget=subprocess.run(['python3',str(ROOT/'experiments/audit_baseline_information_budget.py')],cwd=ROOT,capture_output=True,text=True);audit=json.loads((ROOT/'results/delegation_transition_pilot/final_readiness/baseline_information_budget_audit.json').read_text());(OUT/'baseline_interface_audit.json').write_text(json.dumps({'archived_b0_sha256':sha(ROOT/'models/action_risk_baseline_phase11.py'),'archived_b1_sha256':sha(ROOT/'models/task_alignment_baseline_phase11.py'),'audit':audit},indent=2)+'\n')
 tests=subprocess.run(['python3','-m','unittest','tests.test_delegation_transition_state_machine','tests.test_forbidden_unsupported_semantics'],cwd=ROOT,capture_output=True,text=True);sem={'tests_pass':tests.returncode==0,'test_output':tests.stderr[-3000:]};(OUT/'dtm_semantics_audit.json').write_text(json.dumps(sem,indent=2)+'\n');summary={'proposed_actions':len(rows),'b0_behavior_equivalence':sum(x['b0_equal'] for x in rows)/len(rows),'b1_behavior_equivalence':sum(x['b1_equal'] for x in rows)/len(rows),'baseline_information_budget_pass':audit['pass'],'dtm_semantics_pass':sem['tests_pass'],'performance_inspected':False};(OUT/'phase11b_summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'PHASE11B_REPORT.md').write_text('# Phase 1.1b Interface Hardening\n\n```json\n'+json.dumps(summary,indent=2)+'\n```\n\nThis phase validates interface and output equivalence only; it computes no monitor-performance metric.\n');print(json.dumps(summary,indent=2));return 0 if all((summary['b0_behavior_equivalence']==1,summary['b1_behavior_equivalence']==1,audit['pass'],sem['tests_pass'])) else 1
if __name__=='__main__':raise SystemExit(main())
