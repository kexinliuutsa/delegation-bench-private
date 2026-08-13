#!/usr/bin/env python3
"""Align real control/treatment action sequences without assigning source labels."""
from __future__ import annotations
import argparse,json,re,shlex
from pathlib import Path

def parts(event):
 action=event['action'].strip();tool=event.get('tool','unknown');raw_arguments=event.get('arguments','');
 try:decoded=json.loads(raw_arguments) if isinstance(raw_arguments,str) and raw_arguments.startswith('{') else None
 except json.JSONDecodeError:decoded=None
 tokens=shlex.split(action) if action else [];kind=tool if tool!='unknown' else (tokens[0] if tokens else '');args=tokens[1:];target=(decoded or {}).get('path') or (decoded or {}).get('command') or next((x for x in args if not x.startswith('-')),'');return {'type':kind,'target':target,'tool':tool,'arguments':raw_arguments or ' '.join(args)}
def score(left,right):
 a,b=parts(left),parts(right);return .35*(a['type']==b['type'])+.25*(a['target']==b['target'] and bool(a['target']))+.2*(a['tool']==b['tool'])+.2*(a['arguments']==b['arguments'])
def align(control,treatment):
 n,m=len(control),len(treatment);dp=[[0.]*(m+1) for _ in range(n+1)];back={}
 for i in range(1,n+1):
  for j in range(1,m+1):
   candidates=((dp[i-1][j-1]+score(control[i-1],treatment[j-1]),'pair'),(dp[i-1][j]-.2,'control'),(dp[i][j-1]-.2,'new'));dp[i][j],back[i,j]=max(candidates)
 output=[];i,j=n,m
 while i or j:
  if i and j:move=back[i,j]
  elif i:move='control'
  else:move='new'
  if move=='pair':
   similarity=score(control[i-1],treatment[j-1]);relation='MATCHED' if similarity>=.8 else 'MODIFIED';output.append({'control_step':i,'treatment_step':j,'relation':relation,'comparison':{'score':round(similarity,4),'control':parts(control[i-1]),'treatment':parts(treatment[j-1])}});i-=1;j-=1
  elif move=='control':i-=1
  else:output.append({'control_step':None,'treatment_step':j,'relation':'NEW','comparison':None});j-=1
 return list(reversed(output))
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--raw-dir',type=Path,default=root/'results/authority_source_collection/raw');p.add_argument('--output',type=Path,default=root/'results/authority_source_collection/alignments.json');a=p.parse_args();pairs={}
 for path in a.raw_dir.glob('*.json'):
  data=json.loads(path.read_text());pairs.setdefault(data['pair_id'],{})[data['condition']]=data
 results=[]
 for pair,conditions in sorted(pairs.items()):
  if set(conditions)!={'control','treatment'}:continue
  results.append({'pair_id':pair,'step_alignment':align(conditions['control']['steps'],conditions['treatment']['steps'])})
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(results,indent=2));print(json.dumps({'completed_pairs_aligned':len(results),'labels_assigned':False},indent=2))
if __name__=='__main__':main()
