#!/usr/bin/env python3
"""Experiment 38: contrastive delegation-transition representation."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,random,sys
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from models.delegation_state import DelegationState
from models.delegation_transition_encoder import DelegationTransitionEncoder,TransitionExample,cosine,transition_signature
from models.risk_emergence_model import ObservableEvent

TRANSITIONS=(
 ('internal_external',DelegationState('local','observe','private','session','none'),DelegationState('external','modify','private','persistent','communication'),('send email attachment','forward document','relay report')),
 ('observe_delete',DelegationState('local','observe','private','session','none'),DelegationState('local','delete','private','persistent','irreversible'),('delete file','erase artifact','remove stored object')),
 ('observe_transaction',DelegationState('website','observe','public','temporary','none'),DelegationState('account','transaction','user_data','persistent','financial'),('submit purchase','complete order','confirm acquisition')),
 ('session_persistent',DelegationState('account','modify','user_data','session','none'),DelegationState('account','modify','user_data','persistent','none'),('save settings','persist preferences','commit configuration')),
 ('no_change',DelegationState('local','observe','private','session','none'),DelegationState('local','observe','private','session','none'),('read another file','inspect next artifact','view second document')),
)

def event(action,state):return ObservableEvent(action,'Operation feedback observed.',action.split()[0],state.to_dict())
def examples(surface_index,count):
 output=[]
 for name,before,after,actions in TRANSITIONS:
  for i in range(count):output.append((name,TransitionExample(f'Complete the requested workflow item {i}.',event('inspect initial object',before),event(actions[surface_index],after))))
 return output

def stable(value,mod):return int.from_bytes(hashlib.blake2b(value.encode(),digest_size=8).digest(),'big')%mod
def action_vector(x):
 words=x.current.action.lower().split();return tuple(float(stable(word,97))/97 for word in (words+[''])[:2])
def capability_vector(x):return tuple(float(stable(x.current.capability,8)==i) for i in range(8))
def state_delta_vector(x):
 sig=transition_signature(x.previous,x.current);return tuple(float(any(key in edge for edge in sig)) for key in ('resource_scope','operation_scope','information_scope','persistence_level','external_effect'))

def recall_at(labels,train_labels,test_vectors,train_vectors,k):
 hits=[]
 for label,z in zip(labels,test_vectors):neighbors=sorted(range(len(train_vectors)),key=lambda i:cosine(z,train_vectors[i]),reverse=True)[:k];hits.append(any(train_labels[i]==label for i in neighbors))
 return mean(hits)

def clusters(vectors,k,seed=38):
 centers=[list(vectors[i]) for i in random.Random(seed).sample(range(len(vectors)),k)];assign=[0]*len(vectors)
 for _ in range(20):
  assign=[max(range(k),key=lambda c:cosine(v,centers[c])) for v in vectors]
  for c in range(k):
   members=[vectors[i] for i,a in enumerate(assign) if a==c]
   if members:centers[c]=[mean(x) for x in zip(*members)]
 return assign
def purity(labels,assign):
 groups=defaultdict(list)
 for label,c in zip(labels,assign):groups[c].append(label)
 return sum(max(Counter(x).values()) for x in groups.values())/len(labels)
def nmi(labels,assign):
 n=len(labels);lc=Counter(labels);cc=Counter(assign);joint=Counter(zip(labels,assign));mi=sum(v/n*math.log((v*n)/(lc[l]*cc[c])+1e-12) for (l,c),v in joint.items());hl=-sum(v/n*math.log(v/n) for v in lc.values());hc=-sum(v/n*math.log(v/n) for v in cc.values());return mi/math.sqrt(hl*hc) if hl and hc else 0

def recombinations():
 specs=(
  ('share calendar permanently',DelegationState('local','observe','private','session','none'),DelegationState('external','modify','private','persistent','irreversible')),
  ('make irreversible purchase',DelegationState('website','observe','public','temporary','none'),DelegationState('account','transaction','user_data','persistent','irreversible')),
  ('publish persistent configuration',DelegationState('account','modify','user_data','session','none'),DelegationState('external','modify','user_data','persistent','communication')),
 )
 return [TransitionExample('Complete the requested composite workflow.',event('inspect initial object',before),event(action,after)) for action,before,after in specs]

def component_recall(queries,query_vectors,train_examples,train_vectors,k=5):
 scores=[]
 for query,z in zip(queries,query_vectors):
  wanted=set(transition_signature(query.previous,query.current));neighbors=sorted(range(len(train_vectors)),key=lambda i:cosine(z,train_vectors[i]),reverse=True)[:k];found=set()
  for i in neighbors:found.update(transition_signature(train_examples[i].previous,train_examples[i].current))
  scores.append(len(wanted&found)/len(wanted))
 return mean(scores)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'results/delegation_transition_representation.csv');p.add_argument('--plot',type=Path,default=ROOT/'results/delegation_transition_representation.svg');a=p.parse_args();train=examples(0,30);test=examples(1,20);train_labels=[x[0] for x in train];test_labels=[x[0] for x in test];dte=DelegationTransitionEncoder();dte.fit([x[1] for x in train]);encoders={'Action':action_vector,'Capability':capability_vector,'DBR_state_delta':state_delta_vector,'DTE':dte.encode};rows=[]
 for name,encoder in encoders.items():
  train_z=[encoder(x[1]) for x in train];test_z=[encoder(x[1]) for x in test];queries=recombinations();query_z=[encoder(x) for x in queries];assign=clusters(test_z,len(set(test_labels)));rows.append({'model':name,'recall_at_1':round(recall_at(test_labels,train_labels,test_z,train_z,1),4),'recall_at_5':round(recall_at(test_labels,train_labels,test_z,train_z,5),4),'recombination_component_recall_at_5':round(component_recall(queries,query_z,[x[1] for x in train],train_z),4),'nmi':round(nmi(test_labels,assign),4),'clustering_purity':round(purity(test_labels,assign),4),'latent_dimensions':len(test_z[0]),'train_expressions':'first surface form','test_expressions':'held-out paraphrase'})
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 fields=(('recall_at_1','Recall@1'),('recall_at_5','Recall@5'),('nmi','NMI'),('clustering_purity','Purity'));w,h,left,top,pw,ph=980,500,75,55,840,340;colors=['#64748b','#f59e0b','#8b5cf6','#dc2626'];parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">','<rect width="100%" height="100%" fill="white"/>','<text x="490" y="25" text-anchor="middle" font-family="sans-serif" font-size="18">Delegation Transition Representation</text>']
 for tick in range(6):v=tick/5;y=top+ph*(1-v);parts += [f'<line x1="{left}" y1="{y}" x2="{left+pw}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.1f}</text>']
 for fi,(field,title) in enumerate(fields):
  center=left+pw/4*(fi+.5);parts.append(f'<text x="{center}" y="{top+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="10">{title}</text>')
  for i,row in enumerate(rows):value=float(row[field]);x=center+(i-1.5)*36-13;y=top+ph*(1-value);parts.append(f'<rect x="{x}" y="{y}" width="26" height="{top+ph-y}" fill="{colors[i]}"/>')
 for i,row in enumerate(rows):x=40+(i%2)*450;y=h-40+(i//2)*17;parts += [f'<rect x="{x}" y="{y-10}" width="12" height="12" fill="{colors[i]}"/>',f'<text x="{x+17}" y="{y}" font-family="sans-serif" font-size="10">{row["model"]}</text>']
 parts.append('</svg>');a.plot.write_text('\n'.join(parts),encoding='utf-8');print(json.dumps({'results':rows,'positive_pairs':'same automatically derived observable state-transition signature','negative_pairs':'different observable state-transition signature','labels_used':'no risk, factor, boundary, or attribution labels'},indent=2))
if __name__=='__main__':main()
