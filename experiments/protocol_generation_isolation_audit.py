#!/usr/bin/env python3
"""Experiment 68: audit paired generation isolation from persisted evidence."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UNKNOWN="UNKNOWN"

def pairs_from_manifest(path):
 data=json.loads(path.read_text());pairs={}
 for job in data["jobs"]:pairs.setdefault(job["pair_id"],{})[job["condition"]]=job
 return pairs
def normalized(path):
 pairs={}
 for line in path.read_text().splitlines():
  row=json.loads(line);pairs.setdefault(row["pair_id"],{})[row["condition"]]=row
 return pairs
def raw_pair(base,pair):
 return {role:json.loads((base/f"{pair}_{role}.json").read_text()) for role in ("control","treatment")}
def equality(a,b,key):return a.get(key,UNKNOWN)==b.get(key,UNKNOWN) if key in a and key in b else UNKNOWN
def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'results/protocol_validity');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
 norm=normalized(ROOT/'results/multi_agent_delegation/normalized_rollouts.jsonl');specs=[
  ('coding',ROOT/'results/environment_influence_expansion/collection_manifest.json',ROOT/'results/environment_influence_expansion/integrity_audit.json',ROOT/'results/environment_influence_expansion/raw'),
  ('web',ROOT/'results/web_delegation/collection_manifest.json',ROOT/'results/web_delegation/integrity_audit.json',ROOT/'results/web_delegation/raw')]
 rows=[]
 for agent_type,manifest_path,integrity_path,raw_dir in specs:
  manifest=pairs_from_manifest(manifest_path);integrity=json.loads(integrity_path.read_text());audit_key='pair_integrity' if 'pair_integrity' in integrity else 'pairs';audits={x['pair_id']:x for x in integrity[audit_key]}
  for pair_id,roles in sorted(manifest.items()):
   c,t=roles['control'],roles['treatment'];nc,nt=norm[pair_id]['control'],norm[pair_id]['treatment'];raw=raw_pair(raw_dir,pair_id);ia=audits[pair_id]
   task_equal=equality(c,t,'task');task_id_equal=equality(c,t,'task_id');seed_equal=equality(c,t,'seed');model_equal=equality(raw['control'],raw['treatment'],'model')
   agent_equal=all(nc.get(k)==nt.get(k) for k in ('agent_id','agent_type','agent_model'))
   channel_key='observation_channels' if 'observation_channels' in c else 'intervention_channel';channel_equal=equality(c,t,channel_key)
   if agent_type=='coding':
    non_hash=bool(ia.get('repositories_equal_excluding_intervention')) and ia.get('control_hash_excluding_intervention')==ia.get('treatment_hash_excluding_intervention');declared=bool(ia.get('difference_matches_declaration'))
   else:
    # The persisted site integrity audit identifies site.json as the sole initial
    # artifact and verifies that it contains the declared intervention contrast.
    non_hash=bool(ia.get('single_intervention_artifact')=='site.json');declared=bool(ia.get('intervention_present'))
   known_checks=[task_equal,task_id_equal,seed_equal,model_equal,agent_equal,channel_equal,non_hash,declared]
   unknown_fields=['runner_configuration','model_configuration','system_prompt','tool_definitions','max_steps','prompt_prefix','prompt_suffix']
   unexpected=any(value is False for value in known_checks)
   clean=not unexpected and not unknown_fields
   details={'evidence':{'manifest':str(manifest_path.relative_to(ROOT)),'integrity_audit':str(integrity_path.relative_to(ROOT)),'raw_control':str((raw_dir/f'{pair_id}_control.json').relative_to(ROOT)),'raw_treatment':str((raw_dir/f'{pair_id}_treatment.json').relative_to(ROOT))},'A_pre_treatment':{'task_id_equal':task_id_equal,'agent_metadata_equal':agent_equal,'observation_channel_equal':channel_equal,'unknown_fields':unknown_fields},'B_declared_intervention':{'declared_intervention_only':declared,'non_intervention_hash_equal':non_hash,'declared_difference_files':ia.get('declared_intervention_files',[ia.get('single_intervention_artifact')]),'actual_difference_files':ia.get('actual_difference_files',[ia.get('single_intervention_artifact')]),'control_hash_excluding_intervention':ia.get('control_hash_excluding_intervention',UNKNOWN),'treatment_hash_excluding_intervention':ia.get('treatment_hash_excluding_intervention',UNKNOWN),'control_declared_artifact_hash':ia.get('control_hash',UNKNOWN),'treatment_declared_artifact_hash':ia.get('treatment_hash',UNKNOWN)},'C_post_treatment':{'trajectory_length_control':len(raw['control']['steps']),'trajectory_length_treatment':len(raw['treatment']['steps']),'classification':'POST_TREATMENT_OUTCOME_NOT_CONFOUNDER'}}
   rows.append({'pair_id':pair_id,'agent_type':agent_type,'task_equal':task_equal,'seed_equal':seed_equal,'model_equal':model_equal,'runner_equal':UNKNOWN,'system_prompt_equal':UNKNOWN,'tool_config_equal':UNKNOWN,'initial_state_equal':non_hash and declared,'non_intervention_hash_equal':non_hash,'declared_intervention_only':declared,'unexpected_pre_treatment_difference':unexpected if unexpected else UNKNOWN,'details':json.dumps(details,sort_keys=True,separators=(',',':')),'_clean':clean,'_unknown_fields':unknown_fields})
 outrows=[{k:v for k,v in row.items() if not k.startswith('_')} for row in rows];
 with (a.output_dir/'generation_isolation_audit.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(outrows[0]));w.writeheader();w.writerows(outrows)
 no_unknown=all(not x['_unknown_fields'] for x in rows);no_unexpected=all(x['unexpected_pre_treatment_difference'] is not True for x in rows);clean=sum(x['_clean'] for x in rows)
 summary={'total_pairs':len(rows),'clean_pairs':clean,'pairs_with_unexpected_pre_treatment_difference':sum(x['unexpected_pre_treatment_difference'] is True for x in rows),'pairs_with_unknown_generation_fields':sum(bool(x['_unknown_fields']) for x in rows),'coding_clean_rate':sum(x['_clean'] and x['agent_type']=='coding' for x in rows)/48,'web_clean_rate':sum(x['_clean'] and x['agent_type']=='web' for x in rows)/48,'causal_trajectory_level_claim_supported':bool(no_unknown and no_unexpected and clean==len(rows)),'known_evidence_supports_intervention_only_difference':no_unexpected,'unknown_fields_per_pair':['runner_configuration','model_configuration','system_prompt','tool_definitions','max_steps','prompt_prefix','prompt_suffix'],'post_treatment_variables_excluded_from_confound_check':['trajectory_length','number_of_actions','tool_counts','final_state'],'within_trajectory_temporal_onset_claim_supported':False}
 (a.output_dir/'generation_isolation_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
