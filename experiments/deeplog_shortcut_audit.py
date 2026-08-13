#!/usr/bin/env python3
import csv,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'experiments'))
from models.deeplog_delegation import DeepLogDelegation
from experiment75_published_baseline_suite import load_jobs,event_seq,auc
OUT=ROOT/'results/delegation_bench_v1/published_baselines'
def main():
 train=load_jobs({0,1,2});dev=load_jobs({3});ev=load_jobs({4});m=DeepLogDelegation(5).fit([event_seq(x['control']) for x in train.values()]);rows=[]
 for split,data in [('development',dev),('existing_evaluation',ev)]:
  dlc=[];dlt=[];lengthc=[];lengtht=[];freqc=[];freqt=[]
  for x in data.values():
   a=event_seq(x['control']);b=event_seq(x['treatment']);dlc.append(statistics.mean(m.scores(a)));dlt.append(statistics.mean(m.scores(b)));lengthc.append(len(a));lengtht.append(len(b));freqc.append(len(set(a))/len(a));freqt.append(len(set(b))/len(b))
  def corr(x,y):
   mx,my=statistics.mean(x),statistics.mean(y);den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y));return sum((a-mx)*(b-my) for a,b in zip(x,y))/den if den else 0
  rows += [{'split':split,'shortcut':'B_LEN','correlation_with_deeplog':corr(lengthc+lengtht,dlc+dlt),'shortcut_auroc':auc(lengthc,lengtht)},{'split':split,'shortcut':'B_FREQ','correlation_with_deeplog':corr(freqc+freqt,dlc+dlt),'shortcut_auroc':auc(freqc,freqt)},{'split':split,'shortcut':'B_LEN_FREQ','correlation_with_deeplog':corr([a+b for a,b in zip(lengthc+lengtht,freqc+freqt)],dlc+dlt),'shortcut_auroc':auc([a+b for a,b in zip(lengthc,freqc)],[a+b for a,b in zip(lengtht,freqt)])}]
 with (OUT/'deeplog_shortcut_results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
