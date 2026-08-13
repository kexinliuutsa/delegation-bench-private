#!/usr/bin/env python3
"""Hard leakage/freeze audit for PIDR-v1 TRAIN/DEVELOPMENT selection."""
from __future__ import annotations
import ast,hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));sys.path.insert(0,str(ROOT/'experiments'))
from pidr_v1 import PIDRV1
from delegation_bench_v1_common import RESULTS
OUT=RESULTS/'pidr_v1'
def accessed_string_keys(path):
 tree=ast.parse(Path(path).read_text());keys=set()
 for node in ast.walk(tree):
  if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str):keys.add(node.slice.value)
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='get' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):keys.add(node.args[0].value)
 return keys
def main():
 protocol=subprocess.run(['python3',str(ROOT/'experiments/freeze_delegation_bench_v1_protocol.py'),'--verify'],cwd=ROOT,capture_output=True,text=True);artifact=json.loads((OUT/'pidr_v1_model.json').read_text());access=json.loads((OUT/'training_access_log.json').read_text());model=PIDRV1.from_dict(artifact);dummy={'task':'t','paradigm':'coding','previous_actions':[],'previous_tools':[],'previous_observations':[],'previous_capability':'A0_OBSERVE','current_observation':'o','current_observation_source':'tool','current_action':'a','current_tool':'read','current_capability':'A0_OBSERVE','normalized_progress':.5,'recent_tool_run_length':0,'recent_action_run_length':0};features=model.feature_dict(dummy);forbidden=['unsafe_label','authority_label','drift_label','source_label','oracle_label','private_reasoning','chain_of_thought'];accessed=accessed_string_keys(ROOT/'models/pidr_v1.py')|accessed_string_keys(ROOT/'experiments/train_pidr_v1.py');checks={'seed_4_never_loaded':not any(x['seed']==4 or re.search(r'_s04(?:_|\.)',x['path']) for x in access['opened_trajectory_paths']),'seed_4_statistics_not_computed':artifact['seed_4_accessed'] is False,'forbidden_labels_unused':not bool(set(forbidden)&accessed),'condition_absent_from_encoder_features':not any(k.startswith('condition') for k in features),'intervention_style_absent_from_encoder_features':not any(k.startswith('intervention_style') for k in features),'scheduled_exposure_absent_from_encoder_features':not any(k.startswith('scheduled_exposure') for k in features),'future_events_absent':all(x not in features for x in ('future_events','future_action')),'private_reasoning_absent':all(x not in features for x in ('private_reasoning','thought')),'threshold_calibration_train_controls_only':json.loads((OUT/'training_report.json').read_text())['pidr_monitor']['threshold_source']=='TRAIN controls only','protocol_hashes_match':protocol.returncode==0};report={'checks':checks,'passed':all(checks.values()),'seed_4_accessed':False,'forbidden_field_accesses':sorted(set(forbidden)&accessed)};(OUT/'leakage_audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
 if report['passed']:
  digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();selected=json.loads((OUT/'selected_model.json').read_text())['selected_config'];marker={'frozen_at':datetime.now(timezone.utc).isoformat(),'selected_hyperparameters':{k:selected[k] for k in ('latent_dimension','lambda_sep','beta_temp','margin','gamma_var')},'model_artifact_sha256':digest(OUT/'pidr_v1_model.json'),'training_script_sha256':digest(ROOT/'experiments/train_pidr_v1.py'),'evaluation_script_sha256':digest(ROOT/'experiments/evaluate_pidr_v1_dev.py'),'statement':'Seed 4 sealed test has not been accessed.'};(OUT/'PIDR_V1_FROZEN').write_text(json.dumps(marker,indent=2)+'\n')
 raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
