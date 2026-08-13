#!/usr/bin/env python3
"""Pre-label quality audit for real paired authority-source rollouts."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
def tokens(text):return set(re.findall(r'[a-z0-9_./-]+',text.lower()))
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();base=root/'results/authority_source_collection';p.add_argument('--manifest',type=Path,default=base/'collection_manifest.json');p.add_argument('--status',type=Path,default=base/'status.json');p.add_argument('--raw-dir',type=Path,default=base/'raw');p.add_argument('--output',type=Path,default=base/'audit.json');a=p.parse_args();manifest=json.loads(a.manifest.read_text());status=json.loads(a.status.read_text());jobs={(x['pair_id'],x['condition']):x for x in manifest['jobs']};integrity={x['pair_id']:x for x in status['pair_integrity']};pairs=sorted({x['pair_id'] for x in status['trajectories']});audits=[]
 for pair in pairs:
  files={condition:a.raw_dir/f'{pair}_{condition}.json' for condition in ('control','treatment')};trajectories={c:json.loads(path.read_text()) for c,path in files.items() if path.exists()};check=integrity[pair];complete=set(trajectories)=={'control','treatment'};seed_match=complete and trajectories['control']['seed']==trajectories['treatment']['seed']==jobs[pair,'control']['seed'];missing_steps=False;labels_absent=True
  for trajectory in trajectories.values():
   missing_steps=missing_steps or [x['step'] for x in trajectory['steps']]!=list(range(1,len(trajectory['steps'])+1)) or any(not x.get('action') for x in trajectory['steps']);serialized=json.dumps(trajectory).lower();labels_absent=labels_absent and all(x not in serialized for x in ('source_label','expected_drift','boundary_label'))
  injection=jobs[pair,'treatment']['environment_content'];wanted=tokens(injection);observed=' '.join(x.get('observation','') for x in trajectories.get('treatment',{}).get('steps',[]));exposure=len(wanted&tokens(observed))/max(1,len(wanted))>=.5
  hard_pass=bool(check['repository_hash_equal_excluding_injection'] and check['injection_only_files'] and complete and seed_match and not missing_steps and labels_absent);audits.append({'pair_id':pair,'A_repository_equal_excluding_injection':check['repository_hash_equal_excluding_injection'],'B_injection_only_difference':bool(check['injection_only_files']),'C_trajectories_exist':complete,'D_injection_observed':exposure,'E_no_missing_steps':not missing_steps,'seed_match':seed_match,'labels_absent':labels_absent,'hard_quality_pass':hard_pass})
 result={'pairs':len(pairs),'hard_quality_pass':sum(x['hard_quality_pass'] for x in audits),'exposure_count':sum(x['D_injection_observed'] for x in audits),'exposure_rate':sum(x['D_injection_observed'] for x in audits)/len(audits) if audits else 0,'pair_audits':audits};a.output.write_text(json.dumps(result,indent=2));print(json.dumps({key:result[key] for key in ('pairs','hard_quality_pass','exposure_count','exposure_rate')},indent=2))
if __name__=='__main__':main()
