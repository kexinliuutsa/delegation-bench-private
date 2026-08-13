#!/usr/bin/env python3
import csv,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'benchmarks/delegation_bench_v1/resistance'; R=ROOT/'results/delegation_bench_v1/resistance_judge_validation'; L=['CONTINUE','HESITATE','REQUEST_CONFIRMATION','REFUSE','ABSTAIN']
def kappa(a,b):
 n=len(a);po=sum(x==y for x,y in zip(a,b))/n;ca=Counter(a);cb=Counter(b);pe=sum(ca[x]*cb[x] for x in L)/(n*n);return (po-pe)/(1-pe) if pe<1 else 1.0
def main():
 pa=B/'human_annotation_A.csv';pb=B/'human_annotation_B.csv'
 if not(pa.exists() and pb.exists()):print('WAITING_FOR_HUMAN_ANNOTATIONS');return 2
 def read(p):
  d={r['sample_id']:r for r in csv.DictReader(p.open())};assert all(x['label'] in L for x in d.values());return d
 a,b=read(pa),read(pb);ids=sorted(set(a)&set(b));aa=[a[i]['label'] for i in ids];bb=[b[i]['label'] for i in ids]
 kap=kappa(aa,bb);binary=lambda x:'RESISTANCE_LIKE' if x in {'HESITATE','REQUEST_CONFIRMATION','REFUSE'} else x
 out={'N':len(ids),'raw_agreement':sum(x==y for x,y in zip(aa,bb))/len(ids),'cohen_kappa':kap,'binary_resistance_kappa':kappa(list(map(binary,aa)),list(map(binary,bb))),'status':'TAXONOMY_NOT_RELIABLE_ENOUGH' if kap<.7 else ('TAXONOMY_MODERATE_AGREEMENT' if kap<.8 else 'HUMAN_AGREEMENT_PASSES')}
 (R/'human_agreement.json').write_text(json.dumps(out,indent=2)+'\n')
 disagreements=[i for i in ids if a[i]['label']!=b[i]['label']]
 with (B/'human_disagreement_packet.csv').open('w',newline='') as f:
  fields=['sample_id','label_A','label_B','evidence_A','evidence_B','adjudicated_label'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({'sample_id':i,'label_A':a[i]['label'],'label_B':b[i]['label'],'evidence_A':a[i]['evidence_span'],'evidence_B':b[i]['evidence_span'],'adjudicated_label':''} for i in disagreements)
 print(json.dumps(out,indent=2))
if __name__=='__main__':sys.exit(main() or 0)
