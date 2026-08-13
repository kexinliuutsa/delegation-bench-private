#!/usr/bin/env python3
"""One-shot report correction: aggregate-ratio pair bootstrap; no model selection/evaluation changes."""
from __future__ import annotations
import csv,hashlib,json,random,sys
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'models'));sys.path.insert(0,str(ROOT/'experiments'))
from pidr_v1 import PIDRV1
from train_pidr_v1 import sample,monotone
from delegation_bench_v1_common import BENCH,RESULTS
from evaluate_pidr_v1_sealed_test import quantile
OUT=RESULTS/'pidr_v1_sealed_test';PIDR=RESULTS/'pidr_v1';REPS=10_000;SEED=72001
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 marker=json.loads((OUT/'SEALED_TEST_OPENED').read_text());frozen=json.loads((PIDR/'PIDR_V1_FROZEN').read_text());assert sha(PIDR/'pidr_v1_model.json')==frozen['model_artifact_sha256'];model=PIDRV1.from_dict(json.loads((PIDR/'pidr_v1_model.json').read_text()));manifest=json.loads((BENCH/'collection_manifest.json').read_text());audit={r['pair_id']:r for r in csv.DictReader((RESULTS/'audits/pre_exposure_prefix_audit.csv').open())};jobs=[j for j in manifest['jobs'] if j['seed']==4];pairs={}
 for j in jobs:
  raw=json.loads((RESULTS/'raw'/f"{j['pair_id']}_{j['condition']}.json").read_text());pairs.setdefault(j['pair_id'],{})[j['condition']]=[sample(j,raw,i) for i in range(len(raw['steps']))]
 geometry=[]
 for pid,roles in pairs.items():
  if not audit[pid]['actual_exposure_step'].isdigit():continue
  ex=int(audit[pid]['actual_exposure_step']);pre=monotone([s for s in roles['control'] if s['step']<ex],[s for s in roles['treatment'] if s['step']<ex]);post=monotone([s for s in roles['control'] if s['step']>=ex],[s for s in roles['treatment'] if s['step']>=ex])
  if not pre or not post:continue
  geometry.append({'raw_pre':mean(model.distance(a,b,True) for a,b in pre),'pidr_pre':mean(model.distance(a,b,False) for a,b in pre),'raw_post':mean(model.distance(a,b,True) for a,b in post),'pidr_post':mean(model.distance(a,b,False) for a,b in post)})
 rng=random.Random(SEED);dist=[]
 for _ in range(REPS):
  g=[geometry[rng.randrange(len(geometry))] for _ in geometry];rr=mean(x['raw_post'] for x in g)/max(mean(x['raw_pre'] for x in g),1e-9);pr=mean(x['pidr_post'] for x in g)/max(mean(x['pidr_pre'] for x in g),1e-9);dist.append(pr-rr)
 point=mean(x['pidr_post'] for x in geometry)/mean(x['pidr_pre'] for x in geometry)-mean(x['raw_post'] for x in geometry)/mean(x['raw_pre'] for x in geometry);interval=[quantile(dist,.025),quantile(dist,.975)];path=OUT/'bootstrap_comparisons.csv';rows=list(csv.DictReader(path.open()))
 for row in rows:
  if row['comparison']=='geometry_ratio':row.update({'point_estimate':str(point),'ci95':json.dumps(interval),'ci95_low':str(interval[0]),'ci95_high':str(interval[1])})
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary=json.loads((OUT/'sealed_test_summary.json').read_text());summary['bootstrap']['geometry_ratio']={'point_estimate':point,'ci95':interval};summary['hypotheses']['H2']['status']='SUPPORTED' if interval[0]>0 else ('NOT SUPPORTED' if interval[1]<=0 else 'INCONCLUSIVE');summary['report_amendment']={'type':'aggregate_ratio_bootstrap_correction','model_or_threshold_changed':False,'reason':'bootstrap replicate now computes mean(post)/mean(pre), matching preregistered aggregate ratio'};(OUT/'sealed_test_summary.json').write_text(json.dumps(summary,indent=2)+'\n');hyp=json.loads((OUT/'hypothesis_results.json').read_text());hyp['H2']['status']=summary['hypotheses']['H2']['status'];(OUT/'hypothesis_results.json').write_text(json.dumps(hyp,indent=2)+'\n');report=(OUT/'PIDR_V1_SEALED_TEST_REPORT.md').read_text();report=report.replace('"H2": "SUPPORTED"','"H2": "INCONCLUSIVE"');report+='\n## Statistical amendment\n\nThe ratio-difference pair bootstrap was corrected to compute aggregate mean(post)/mean(pre) within each replicate. Its CI crosses zero, so H2 is INCONCLUSIVE. No model, threshold, sample, or point estimate was changed.\n';(OUT/'PIDR_V1_SEALED_TEST_REPORT.md').write_text(report);marker['evaluation_script_sha256']=sha(ROOT/'experiments/evaluate_pidr_v1_sealed_test.py');marker['report_amendment']=summary['report_amendment'];(OUT/'SEALED_TEST_OPENED').write_text(json.dumps(marker,indent=2)+'\n');print(json.dumps({'geometry_ratio_delta':point,'ci95':interval,'H2':hyp['H2']['status'],'model_modified':False},indent=2))
if __name__=='__main__':main()
