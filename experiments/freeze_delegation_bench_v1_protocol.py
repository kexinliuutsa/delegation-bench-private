#!/usr/bin/env python3
"""Freeze and hash the audited Delegation Bench v1 protocol."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from delegation_bench_v1_common import BENCH,RESULTS,sha
FILES=['collection_manifest.json','split.json','statistical_plan.json','task_catalog.json','intervention_catalog.json','paradigm_catalog.json','schema.json']
def hashes():return {name:sha((BENCH/name).read_bytes()) for name in FILES}
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();output=RESULTS/'audits/FROZEN_PROTOCOL_SHA256.json';marker=BENCH/'PROTOCOL_FROZEN'
 if a.verify:
  if not output.exists() or not marker.exists():raise SystemExit('protocol is not frozen')
  expected=json.loads(output.read_text())['files'];actual=hashes()
  if actual!=expected:raise SystemExit('FROZEN PROTOCOL HASH MISMATCH: explicit protocol revision required')
  print(json.dumps({'protocol_frozen':True,'hashes_match':True},indent=2));return
 gen=json.loads((RESULTS/'audits/generation_isolation_summary.json').read_text());pre=json.loads((RESULTS/'audits/pre_rollout_exposure_audit.json').read_text())
 if gen.get('passed_pairs')!=160 or gen.get('hard_fail') or not pre.get('all_pairs_pass') or pre.get('passed_pairs')!=160:raise SystemExit('cannot freeze: required 160/160 audits did not pass')
 timestamp=datetime.now(timezone.utc).isoformat();report={'benchmark_version':'v1','frozen_at':timestamp,'planned_pairs':160,'planned_trajectories':320,'files':hashes()};output.write_text(json.dumps(report,indent=2)+'\n');marker.write_text(f'benchmark_version=v1\nfrozen_at={timestamp}\nprotocol_hash_manifest={output.relative_to(RESULTS.parent.parent)}\n');print(json.dumps({'protocol_frozen':True,'files_hashed':len(FILES),'frozen_at':timestamp},indent=2))
if __name__=='__main__':main()
