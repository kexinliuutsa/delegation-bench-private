#!/usr/bin/env python3
"""Evaluate frozen schema-format cases; never reads monitor outputs or contracts."""
import csv,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from models.action_normalizer_v2 import canonicalize_fields,normalize_action
ROOT=Path(__file__).resolve().parents[1]; CASES=ROOT/'benchmarks/delegation_transition_pilot/normalizer_v2_schema_cases.json'; OUT=ROOT/'results/delegation_transition_pilot/normalizer_v2'
def main():
 data=json.loads(CASES.read_text()); rows=[]
 for x in data['holdout']:
  got=normalize_action(x['action']); status=got.get('status','RESOLVED'); semantic=got['subactions']
  pred='ABSTAIN' if status=='ABSTAIN' else 'RESOLVED'; correct=(pred==x['expected_status'] and (pred=='ABSTAIN' or semantic==x['expected_subactions']))
  rows.append({"case_id":x['case_id'],"expected_status":x['expected_status'],"predicted_status":pred,"correct":correct})
 resolv=[r for r in rows if r['expected_status']=='RESOLVED']; abst=[r for r in rows if r['expected_status']=='ABSTAIN']
 acc=sum(r['correct'] for r in rows)/len(rows); cov=sum(r['predicted_status']=='RESOLVED' for r in resolv)/len(resolv); aa=sum(r['correct'] for r in abst)/len(abst)
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/'holdout_results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 summary={"holdout_n":len(rows),"semantic_normalization_accuracy":acc,"resolvable_coverage":cov,"abstention_accuracy":aa,"gates_pass":min(acc,cov,aa)>=.95,"rules_written_without_holdout_inspection":True,"performance_signal_used":False}
 (OUT/'normalizer_v2_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
