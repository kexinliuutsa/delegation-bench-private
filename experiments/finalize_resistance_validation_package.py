#!/usr/bin/env python3
"""Record integrity, judge freeze, joinability, and the Experiment-82A.2 wait state."""
import hashlib,json,random,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BENCH=ROOT/'benchmarks/delegation_bench_v1';B=BENCH/'resistance';RES=ROOT/'results/delegation_bench_v1';R=RES/'resistance_judge_validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 sample=json.loads((B/'human_validation_sample.json').read_text()); ids=[x['sample_id'] for x in sample['examples']];rng=random.Random(82130);subset=sorted(rng.sample(ids,30))
 (B/'judge_stability_subset.json').write_text(json.dumps({'status':'FROZEN_BEFORE_HUMAN_GOLD','seed':82130,'N':30,'sample_ids':subset},indent=2)+'\n')
 raw=sorted((RES/'raw').glob('*.json'))
 fixed=[ROOT/'models/refusal_rule_baseline.py',BENCH/'refusal/refusal_rule_challenge_set.json',RES/'refusal_audit_phase0/EXPERIMENT_82A_PHASE0_REPORT.md',RES/'refusal_audit_phase0/EXPERIMENT_82A_1_REPORT.md']
 prompt=B/'RESISTANCE_JUDGE_V1_PROMPT.md'
 hist={'experiment':'82A.2','historical_status_preserved':{'82A_phase0':'REFUSAL_SIGNAL_TOO_SPARSE','82A_1':'RULE_SPECIFICITY_INSUFFICIENT; frozen rule failed semantic validation'},
  'historical_benchmark_modified':False,'fixed_artifact_hashes':{str(p.relative_to(ROOT)):sha(p) for p in fixed},
  'raw_trajectory_count':len(raw),'raw_trajectory_hashes':{p.name:sha(p) for p in raw},
  'judge_model_freeze':{'provider':'OpenAI','model_identifier':'gpt-5','temperature':0,'max_tokens':180,'prompt_sha256':sha(prompt),'selected_before_validation_labels':True},
  'new_rollouts':0,'pidr_values_inspected':False,'scientific_effects_inspected':False}
 (R/'historical_integrity.json').write_text(json.dumps(hist,indent=2)+'\n')
 # Identifier-only joinability: never import or read PIDR score tables.
 normalized=RES/'normalized/trajectories.jsonl'; available=set()
 if normalized.exists():
  for line in normalized.read_text().splitlines():available.add(json.loads(line).get('trajectory_id'))
 manifest=json.loads((BENCH/'collection_manifest.json').read_text()); expected={j['trajectory_id'] for j in manifest['jobs']}
 join={'PIDR_JOINABLE':'YES' if expected<=available else 'NO','trajectory_ids_expected':len(expected),'trajectory_ids_available_in_frozen_normalized_index':len(available),'joinable_ids':len(expected&available),'join_rate':len(expected&available)/len(expected),'pidr_values_loaded':False,'pidr_values_inspected':False}
 (R/'pidr_joinability_audit.json').write_text(json.dumps(join,indent=2)+'\n')
 a=B/'human_annotation_A.csv';b=B/'human_annotation_B.csv';status='WAITING_FOR_HUMAN_ANNOTATIONS' if not(a.exists() and b.exists()) else 'HUMAN_ANNOTATIONS_AVAILABLE_PENDING_AGREEMENT_EVALUATION'
 summary={'experiment':'82A.2','status':status,'validation_sample_N':sample['n'],'sample_sha256':sample['examples_sha256'],'human_annotation_A_available':a.exists(),'human_annotation_B_available':b.exists(),'judge_executed':False,'treatment_control_effect_inspected':False,'intervention_style_effect_inspected':False,'pidr_values_inspected':False,'experiment_82B_launched':False,'pidr_joinable':join['PIDR_JOINABLE']}
 (R/'validation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 counts={}
 for row in csv.DictReader((R/'sample_distribution.csv').open()):counts.setdefault(row['dimension'],{})[row['level']]=int(row['N'])
 report=f'''# Experiment 82A.2 — Human-Grounded Resistance Measurement Validation

This run created the frozen measurement-validation package and stopped before semantic evaluation because two independent human annotation streams are not present.

- Real decision-point sample: {sample['n']} (SHA256 scope hash `{sample['examples_sha256']}`)
- Condition: {counts['condition']}
- Paradigm: {counts['paradigm']}
- Intervention style: {counts['intervention_style']}
- Temporal position: {counts['temporal_position']}
- PIDR joinable by identifier: {join['PIDR_JOINABLE']}; values inspected: NO
- LLM judge calls: 0

Final status: **{status}**. Human-human agreement, judge stability, and rule/LLM/hybrid validation outputs have not been created. Experiment 82B was not launched.
'''
 (R/'EXPERIMENT_82A_2_REPORT.md').write_text(report)
 print(json.dumps({'summary':summary,'distribution':counts,'annotation_packet_A':str(B/'annotation_packet_A.csv'),'annotation_packet_B':str(B/'annotation_packet_B.csv'),'instructions':str(B/'ANNOTATION_INSTRUCTIONS.md')},indent=2))
if __name__=='__main__':main()
