#!/usr/bin/env python3
"""Build blinded >=20% capability-only annotation packet after collection."""
import csv,hashlib,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results/delegation_transition_replication_v21';SEED=802021
def main():
 rows=[]
 for p in sorted((R/'raw').glob('*.json')):
  d=json.loads(p.read_text())
  for s in d['steps']:
   if set(s['mapped_capabilities'])!={'none'}:rows.append({'sample_id':hashlib.sha256(f"{d['trajectory_id']}:{s['step_index']}".encode()).hexdigest()[:16],'proposed_action':json.dumps(s['proposed_action'],sort_keys=True),'annotator_1_capabilities':'','annotator_2_capabilities':''})
 r=random.Random(SEED);r.shuffle(rows);sample=rows[:max(1,(len(rows)+4)//5)];out=R/'human_mapping_audit_packet.csv';out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=sample[0]);w.writeheader();w.writerows(sample)
 print(json.dumps({'seed':SEED,'substantive_actions':len(rows),'sampled':len(sample),'fraction':len(sample)/len(rows)}))
if __name__=='__main__':main()
