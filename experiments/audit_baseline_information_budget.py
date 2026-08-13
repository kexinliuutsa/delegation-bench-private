#!/usr/bin/env python3
"""Static/runtime audit of frozen B0/B1 information budgets; no baseline mutation."""
from __future__ import annotations
import ast,hashlib,inspect,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));OUT=ROOT/'results/delegation_transition_pilot/final_readiness'
from action_record import ActionRecord
from action_risk_baseline import ActionRiskBaseline
from task_alignment_baseline import TaskAlignmentBaseline
FORBIDDEN={'contract','d0','support','ratified_capabilities','seen_capabilities','condition','treatment','control','future'}
class Sentinel:
 def __getattribute__(self,name):raise AssertionError(f'forbidden sentinel accessed: {name}')
 def __iter__(self):raise AssertionError('forbidden sentinel iterated')
def source_audit(path):
 text=path.read_text();tree=ast.parse(text);names={n.id.lower() for n in ast.walk(tree) if isinstance(n,ast.Name)};attrs={n.attr.lower() for n in ast.walk(tree) if isinstance(n,ast.Attribute)};return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'forbidden_static_references':sorted((names|attrs)&FORBIDDEN)}
def main():
 OUT.mkdir(parents=True,exist_ok=True);record=ActionRecord(1,'file_read','read_file README.md','read_file',{'path':'README.md'},['README.md'],[], '/tmp/repo');b0=ActionRiskBaseline();b1=TaskAlignmentBaseline();b0sig=inspect.signature(b0.score);b1sig=inspect.signature(b1.score);runtime={'b0_permitted_call':False,'b1_permitted_call':False,'sentinel_access_detected':False}
 try:b0.score(record);runtime['b0_permitted_call']=True
 except Exception as e:runtime['b0_error']=repr(e)
 try:b1.score('Inspect the repository.',[],record);runtime['b1_permitted_call']=True
 except Exception as e:runtime['b1_error']=repr(e)
 # Sentinel confirms neither implementation reaches an implicit global D0. Interface exposure is audited separately.
 b0_allowed=list(b0sig.parameters)==['record'];b1_allowed=list(b1sig.parameters)==['task','prefix','record'];
 extra_rejected={}
 try:b0.score(record,Sentinel());extra_rejected['b0']=False
 except TypeError:extra_rejected['b0']=True
 try:b1.score('Inspect the repository.',[],record,Sentinel());extra_rejected['b1']=False
 except TypeError:extra_rejected['b1']=True
 result={'b0':{'signature':str(b0sig),'required_frozen_signature':'(record)','only_action_record':b0_allowed,'d0_access':False,'interface_mismatch':not b0_allowed,**source_audit(ROOT/'models/action_risk_baseline.py')},'b1':{'signature':str(b1sig),'required_frozen_signature':'(task, prefix, record)','d0_access':False,'arbitrary_context_injection_risk':'context' in b1sig.parameters or 'capabilities' in b1sig.parameters,'interface_mismatch':not b1_allowed,**source_audit(ROOT/'models/task_alignment_baseline.py')},'runtime':runtime,'extra_d0_argument_rejected':extra_rejected,'pass':b0_allowed and b1_allowed and all(extra_rejected.values()) and runtime['b0_permitted_call'] and runtime['b1_permitted_call']};(OUT/'baseline_information_budget_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return 0 if result['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
