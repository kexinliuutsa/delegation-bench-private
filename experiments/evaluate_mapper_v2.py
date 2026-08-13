#!/usr/bin/env python3
"""Freeze and evaluate Mapper v2 on the independent mapper-development holdout."""
from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));DEV=ROOT/'benchmarks/delegation_transition_pilot/mapper_dev';OUT=ROOT/'results/delegation_transition_pilot/mapper_v2'
from action_record import from_coding_step
from action_capability_mapper_v2 import ActionCapabilityMapperV2
CAPS=['repo_read','repo_write_local','test_execution','dependency_install_declared','dependency_install_new','config_modification','credential_access','external_network','vcs_write_remote','process_control','outside_repo_write']
def rows(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def main():
 OUT.mkdir(parents=True,exist_ok=True);actions={x['action_id']:x for x in rows(DEV/'mapper_dev_actions.jsonl')};labels={x['action_id']:x for x in rows(DEV/'mapper_dev_labels.jsonl')};split=json.loads((DEV/'mapper_dev_split.json').read_text());mapper=ActionCapabilityMapperV2();pred=[]
 for aid in split['holdout']:
  a=actions[aid];r=from_coding_step(a,a['repository_root']);got=mapper.map(r,{'declared_dependencies':['requests']});gold=set(labels[aid]['capabilities']);pred.append({'action_id':aid,'gold':'|'.join(sorted(gold)),'predicted':'|'.join(sorted(got)),'exact':got==gold,'covered':not bool(got&{'unclassified','opaque_execution'}),'unclassified':'unclassified' in got,'opaque':'opaque_execution' in got})
 with (OUT/'mapper_dev_holdout_predictions.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(pred[0]));w.writeheader();w.writerows(pred)
 clear=[a for a in split['holdout'] if labels[a]['annotation_status']=='CLEAR'];tp=fp=fn=0;per=[]
 for cap in CAPS:
  ct=cfp=cfn=0
  for row in pred:
   g=set(row['gold'].split('|'));p=set(row['predicted'].split('|'));ct+=cap in g and cap in p;cfp+=cap not in g and cap in p;cfn+=cap in g and cap not in p
  tp+=ct;fp+=cfp;fn+=cfn;precision=ct/(ct+cfp) if ct+cfp else None;recall=ct/(ct+cfn) if ct+cfn else None;per.append({'capability':cap,'holdout_positive_n':ct+cfn,'precision':precision,'recall':recall,'fewer_than_5':ct+cfn<5})
 with (OUT/'per_capability_metrics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(per[0]));w.writeheader();w.writerows(per)
 micro=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1;f1s=[2*x['precision']*x['recall']/(x['precision']+x['recall']) for x in per if x['precision'] is not None and x['recall'] is not None and x['precision']+x['recall']];summary={'mapper_dev_actions':len(actions),'development_actions':len(split['development']),'holdout_actions':len(split['holdout']),'holdout_exact_set_accuracy':sum(x['exact'] for x in pred)/len(pred),'holdout_micro_f1':micro,'holdout_macro_f1':sum(f1s)/len(f1s),'holdout_coverage':sum(x['covered'] for x in pred)/len(pred),'holdout_unclassified_rate':sum(x['unclassified'] for x in pred)/len(pred),'holdout_opaque_rate':sum(x['opaque'] for x in pred)/len(pred),'holdout_touched_after_rule_development':False};(OUT/'mapper_dev_summary.json').write_text(json.dumps(summary,indent=2)+'\n');source=ROOT/'models/action_capability_mapper_v2.py';normalizer=ROOT/'models/action_normalizer.py';frozen={'mapper_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'normalizer_sha256':hashlib.sha256(normalizer.read_bytes()).hexdigest(),'phase11_diagnostics_used_for_rule_development':False,'dtm_outputs_used':False};(OUT/'MAPPER_V2_FROZEN').write_text(json.dumps(frozen,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
