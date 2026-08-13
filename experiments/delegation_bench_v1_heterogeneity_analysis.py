#!/usr/bin/env python3
import csv,json,math,random,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'results/delegation_bench_v1/confirmatory/pair_level_effects.csv';OUT=ROOT/'results/delegation_bench_v1/heterogeneity';OUT.mkdir(parents=True,exist_ok=True)
def quant(x,p):a=sorted(x);z=(len(a)-1)*p;i=int(z);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(z-i)
def main():
 rows=list(csv.DictReader(SRC.open()));dims=[('Paradigm','paradigm'),('Intervention Style','intervention_style'),('Task Family','task_family'),('Exposure Step','actual_exposure_step')];cells=[];effects=[];rng=random.Random(75010)
 for label,key in dims:
  groups=defaultdict(list)
  for r in rows:
   if r['actual_exposure_step']:groups[r[key]].append(float(r['delta_action']))
  for val,x in sorted(groups.items()):
   n=len(x);flag='VERY_LOW_N' if n<5 else 'LOW_N' if n<10 else 'ADEQUATE';cells.append({'dimension':label,'cell':val,'N':n,'small_cell_flag':flag});bs=[statistics.mean([x[rng.randrange(n)] for _ in x]) for _ in range(10000)];effects.append({'analysis_status':'EXPLORATORY_HETEROGENEITY_ANALYSIS','dimension':label,'level':val,'N':n,'effect_estimate':statistics.mean(x),'ci95_low':quant(bs,.025),'ci95_high':quant(bs,.975),'small_cell_flag':flag})
 for path,data in [(OUT/'cell_sample_sizes.csv',cells),(OUT/'heterogeneity_effects.csv',effects)]:
  with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
 summary={'status':'EXPLORATORY_HETEROGENEITY_ANALYSIS','pairs_with_exposure':len([r for r in rows if r['actual_exposure_step']]),'sparse_cells':sum(x['small_cell_flag']!='ADEQUATE' for x in cells),'interpretation':'Descriptive main-effect summaries only; no saturated interactions or causal style ranking.'};(OUT/'heterogeneity_summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'HETEROGENEITY_REPORT.md').write_text('# Exploratory Heterogeneity Analysis\n\nDescriptive pair-level bootstrap estimates by paradigm, intervention style, task family, and actual exposure step. Cells below 5 are VERY_LOW_N and below 10 LOW_N. This does not establish causal differences among styles or families.\n')
if __name__=='__main__':main()
