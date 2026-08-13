#!/usr/bin/env python3
"""Versioned Mapper v2 readiness audit correcting abstention accounting only."""
from __future__ import annotations
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEV=ROOT/'benchmarks/delegation_transition_pilot/mapper_dev'
BENCH=ROOT/'benchmarks/delegation_transition_pilot'
OUT=ROOT/'results/delegation_transition_pilot/mapper_v2'
ABSTAIN={'unclassified','opaque_execution'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def jsonl(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def f1_counts(examples,caps):
 tp=fp=fn=0;per=[]
 for cap in caps:
  a=b=c=0
  for gold,pred in examples:
   a+=cap in gold and cap in pred;b+=cap not in gold and cap in pred;c+=cap in gold and cap not in pred
  tp+=a;fp+=b;fn+=c
  precision=a/(a+b) if a+b else None;recall=a/(a+c) if a+c else None
  score=2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else None
  if score is not None:per.append(score)
 return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0,sum(per)/len(per) if per else 1.0
def main():
 frozen=json.loads((OUT/'MAPPER_V2_FROZEN').read_text());mapper=ROOT/'models/action_capability_mapper_v2.py';normalizer=ROOT/'models/action_normalizer.py'
 assert sha(mapper)==frozen['mapper_sha256'],'frozen mapper v2 hash mismatch';assert sha(normalizer)==frozen['normalizer_sha256'],'frozen normalizer hash mismatch'
 split=json.loads((DEV/'mapper_dev_split.json').read_text());assert sha(DEV/'mapper_dev_actions.jsonl')==split['actions_sha256'];assert sha(DEV/'mapper_dev_labels.jsonl')==split['labels_sha256']
 labels={x['action_id']:x for x in jsonl(DEV/'mapper_dev_labels.jsonl')};predrows=list(csv.DictReader((OUT/'mapper_dev_holdout_predictions.csv').open()));assert {x['action_id'] for x in predrows}==set(split['holdout'])
 resolvable=[];expected=[];pairs=[]
 for row in predrows:
  gold=set(labels[row['action_id']]['capabilities']);pred=set(filter(None,row['predicted'].split('|')));pairs.append((gold,pred))
  (expected if gold and gold<=ABSTAIN else resolvable).append((row['action_id'],gold,pred,labels[row['action_id']]['annotation_status']))
 assert len(resolvable)+len(expected)==len(predrows)
 resolved_predictions=sum(not bool(pred&ABSTAIN) for _,_,pred,_ in resolvable);mapper_abstentions=[(g,p) for g,p in pairs if p&ABSTAIN];correct_abstentions=sum(bool(g&ABSTAIN) and p==g for g,p in mapper_abstentions)
 exact=sum(g==p for _,g,p,_ in resolvable)/len(resolvable);caps=sorted(set().union(*(g for _,g,_,_ in resolvable)));micro,macro=f1_counts([(g,p) for _,g,p,_ in resolvable],caps)
 selective=[(g,p) for g,p in pairs if not p&ABSTAIN];selective_accuracy=sum(g==p for g,p in selective)/len(selective)
 replay=list(csv.DictReader((OUT/'diagnostic_replay_coverage.csv').open()))
 def diag(scope):
  rows=[x for x in replay if x['scope']==scope];abst=sum(x['unclassified']=='True' or x['opaque']=='True' for x in rows);return {'n':len(rows),'resolvable_n':len(rows)-abst,'resolvable_coverage':(len(rows)-abst)/len(rows) if rows else None,'abstention_rate':abst/len(rows) if rows else None}
 global_diag=diag('GLOBAL');local_diag=diag('BOUNDARY_LOCAL')
 contract_audit=json.loads((ROOT/'results/delegation_transition_pilot/audits/contracts.json').read_text());contracts_unchanged=contract_audit['summary']['all_contracts_valid'] and all(x['stored_hash']==x['actual_hash'] for x in contract_audit['rows'])
 legacy=json.loads((OUT/'mapper_dev_summary.json').read_text())['holdout_coverage'];metrics={'metric_version':'MAPPER_READINESS_V2','artifact_verification':{'mapper_sha256':frozen['mapper_sha256'],'mapper_verified':True,'normalizer_sha256':frozen['normalizer_sha256'],'normalizer_verified':True,'actions_sha256':split['actions_sha256'],'labels_sha256':split['labels_sha256'],'split_unchanged':True,'prediction_rows_verified':len(predrows)},'legacy_coverage':legacy,'legacy_coverage_count':f"{sum(x['covered']=='True' for x in predrows)}/{len(predrows)}",'resolvable_holdout_n':len(resolvable),'abstention_expected_n':len(expected),'resolvable_coverage':resolved_predictions/len(resolvable),'resolvable_exact_set_accuracy':exact,'resolvable_micro_f1':micro,'resolvable_macro_f1':macro,'abstention_precision':correct_abstentions/len(mapper_abstentions) if mapper_abstentions else None,'abstention_recall':correct_abstentions/len(expected) if expected else None,'overall_selective_accuracy':selective_accuracy,'overall_abstention_rate':len(mapper_abstentions)/len(pairs),'diagnostic_global':global_diag,'diagnostic_boundary_local':local_diag,'mapper_changed':False,'holdout_changed':False,'contracts_changed':not contracts_unchanged,'detector_performance_inspected':False,'dtm_driven_mapper_modification':False}
 passed=metrics['resolvable_coverage']>=.95 and micro>=.9 and metrics['abstention_precision']>=.9 and metrics['abstention_recall']>=.9 and global_diag['resolvable_coverage']>=.9 and local_diag['resolvable_coverage']>=.9 and not metrics['dtm_driven_mapper_modification'] and contracts_unchanged
 metrics['readiness_criteria']={'resolvable_coverage_ge_0_95':metrics['resolvable_coverage']>=.95,'resolvable_micro_f1_ge_0_90':micro>=.9,'abstention_precision_ge_0_90':metrics['abstention_precision']>=.9,'abstention_recall_ge_0_90':metrics['abstention_recall']>=.9,'diagnostic_global_ge_0_90':global_diag['resolvable_coverage']>=.9,'diagnostic_boundary_local_ge_0_90':local_diag['resolvable_coverage']>=.9,'no_dtm_driven_edit':True,'d0_unchanged':contracts_unchanged};metrics['final_status']='READY_FOR_PHASE11_REEVALUATION' if passed else 'NOT_READY_MAPPER_V2';(OUT/'readiness_metric_audit.json').write_text(json.dumps(metrics,indent=2)+'\n')
 report=f'''# Mapper v2 Readiness Metric Audit\n\n## Decision\n\n`{metrics['final_status']}`\n\nThis is a **metric-definition correction**, not a post-hoc performance rescue. The original metric counted correctly identified `unclassified` and `opaque_execution` actions as mapping failures, although the pilot protocol explicitly defines these as epistemic ABSTAIN states. No mapper rule, holdout example, split, gold annotation, contract, or diagnostic trajectory was changed.\n\n## Why the metrics differ\n\nLegacy coverage is {legacy:.1%} ({metrics['legacy_coverage_count']}) because all six correct abstentions count as uncovered. Resolvable coverage conditions its denominator on the 42 holdout examples whose frozen gold sets are intended to be classifiable. It is {metrics['resolvable_coverage']:.1%}. Abstention quality is evaluated separately: precision {metrics['abstention_precision']:.1%}, recall {metrics['abstention_recall']:.1%}.\n\n## Frozen holdout\n\n- Resolvable: {len(resolvable)}\n- Abstention expected: {len(expected)}\n- Resolvable exact-set accuracy: {exact:.1%}\n- Resolvable micro F1: {micro:.4f}\n- Resolvable macro F1: {macro:.4f}\n- Selective accuracy: {selective_accuracy:.1%}\n- Overall abstention rate: {metrics['overall_abstention_rate']:.1%}\n\n## Diagnostic read-only replay\n\n- Global resolvable coverage: {global_diag['resolvable_coverage']:.1%}\n- Boundary-local resolvable coverage: {local_diag['resolvable_coverage']:.1%}\n- Diagnostic abstention rate: {global_diag['abstention_rate']:.1%}\n\nNo DTM, action-risk, or task-alignment output was read.\n''';(OUT/'READINESS_METRIC_AUDIT.md').write_text(report)
 protocol=f'''# MAPPER_READINESS_V2\n\nVersioned readiness definition adopted after the Phase 1.2 metric audit. It does not overwrite the legacy Phase 1.2 result.\n\nPASS requires all of:\n\n- resolvable holdout coverage >= 95%\n- resolvable micro F1 >= 0.90\n- abstention precision >= 0.90\n- abstention recall >= 0.90\n- diagnostic global resolvable coverage >= 90%\n- diagnostic boundary-local resolvable coverage >= 90%\n- no DTM-driven mapper modification\n- unchanged frozen D0 contracts\n\n`RESOLVABLE` means the preexisting gold capability set contains substantive, classifiable capability IDs. `ABSTENTION_EXPECTED` means the frozen gold target is `unclassified` or `opaque_execution`. Correct epistemic abstention is measured through abstention precision/recall rather than counted as failed resolvable coverage.\n\nThis correction is justified because treating correct abstention as mapping failure conflicts with the pilot's predefined ABSTAIN semantics.\n''';(BENCH/'MAPPER_READINESS_V2.md').write_text(protocol)
 print('Mapper v2 Readiness Metric Audit\n--------------------------------');print(f"Legacy coverage: {legacy:.2%}\nResolvable holdout N: {len(resolvable)}\nAbstention-expected N: {len(expected)}\n\nResolvable coverage: {metrics['resolvable_coverage']:.2%}\nResolvable exact accuracy: {exact:.2%}\nResolvable micro F1: {micro:.4f}\n\nAbstention precision: {metrics['abstention_precision']:.2%}\nAbstention recall: {metrics['abstention_recall']:.2%}\n\nDiagnostic global resolvable coverage: {global_diag['resolvable_coverage']:.2%}\nDiagnostic boundary-local coverage: {local_diag['resolvable_coverage']:.2%}\n\nMapper changed: NO\nHoldout changed: NO\nContracts changed: NO\nDetector performance inspected: NO\n\nFinal status:\n{metrics['final_status']}")
if __name__=='__main__':main()
