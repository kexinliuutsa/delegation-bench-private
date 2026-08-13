#!/usr/bin/env python3
"""Repeatability audit for deterministic B1 on mapper-development actions only."""
from __future__ import annotations
import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'))
from action_record import from_coding_step
from action_capability_mapper import ActionCapabilityMapper
from task_alignment_baseline import TaskAlignmentBaseline
OUT=ROOT/'results/delegation_transition_pilot/phase11';BENCH=ROOT/'benchmarks/delegation_transition_pilot'
def main():
 cases=json.loads((BENCH/'mapper_dev_cases.json').read_text())['cases'];mapper=ActionCapabilityMapper();judge=TaskAlignmentBaseline();rows=[]
 for c in cases:
  p=c['action'];step={'step':1,'tool':p['tool'],'action':p['tool']+' '+str(p.get('command',p.get('path',''))),'arguments':json.dumps({k:v for k,v in p.items() if k!='tool'})};r=from_coding_step(step,'/tmp/dtp_mapper_dev');labels=[judge.score('Inspect and repair the local repository.',[],r)['decision'] for _ in range(3)];rows.append({'case_id':c['case_id'],'run1':labels[0],'run2':labels[1],'run3':labels[2],'exact_agreement':len(set(labels))==1,'pairwise_agreement':sum(labels[i]==labels[j] for i,j in ((0,1),(0,2),(1,2)))/3,'label_flips':sum(labels[i]!=labels[i-1] for i in (1,2))})
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/'task_alignment_stability.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary={'baseline_type':'deterministic_rule','cases':len(rows),'exact_3_run_agreement':sum(r['exact_agreement'] for r in rows)/len(rows),'pairwise_agreement':sum(r['pairwise_agreement'] for r in rows)/len(rows),'label_flip_count':sum(r['label_flips'] for r in rows)};(OUT/'task_alignment_stability.summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
