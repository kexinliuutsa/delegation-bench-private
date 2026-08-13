#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'))
from delegation_contract import frozen_hash
BENCH=ROOT/'benchmarks/delegation_transition_pilot';RESULTS=ROOT/'results/delegation_transition_pilot'
def main():
 rows=[]
 for p in sorted((BENCH/'contracts').glob('*.yaml')):
  value=json.loads(p.read_text());c=value['delegation_contract'];actual=frozen_hash(value);rows.append({'contract_id':c['contract_id'],'path':str(p),'written_before_rollout':c['written_before_rollout'],'review_status':c['authoring']['review_status'],'stored_hash':c['authoring']['frozen_hash'],'actual_hash':actual,'valid':c['written_before_rollout'] and c['authoring']['review_status']=='frozen' and c['authoring']['frozen_hash']==actual})
 manifest=json.loads((BENCH/'intervention_manifest.json').read_text());leak=any(any(term in json.dumps(j.get('agent_visible_initial',{})).lower() for term in ('contract_id','candidate_capability','expected_support_status','condition')) for j in manifest['jobs']);isolated=True;generation=[]
 for pair in manifest['pairs']:
  jobs=[j for j in manifest['jobs'] if j['pair_id']==pair['pair_id']];a,b=sorted(jobs,key=lambda x:x['condition']);keys=('task','task_family','seed','model','runner','system_prompt_id','tool_schema_id','timeout_seconds','max_steps','initial_repository_fixture','expected_perturbation_step','agent_visible_initial');equal=all(a[k]==b[k] for k in keys);isolated&=equal;generation.append({'pair_id':pair['pair_id'],'generation_equal_except_private_payload':equal})
 summary={'contracts':len(rows),'contracts_frozen':sum(r['valid'] for r in rows),'all_contracts_valid':all(r['valid'] for r in rows),'contract_leakage':leak,'diagnostic_pairs':len(manifest['pairs']),'generation_isolation_protocol_pass':isolated};(RESULTS/'audits').mkdir(parents=True,exist_ok=True);(RESULTS/'audits/contracts.json').write_text(json.dumps({'rows':rows,'generation':generation,'summary':summary},indent=2)+'\n');print(json.dumps(summary,indent=2));return 0 if summary['all_contracts_valid'] and not leak and isolated else 1
if __name__=='__main__':raise SystemExit(main())
