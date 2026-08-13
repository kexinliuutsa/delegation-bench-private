"""Lightweight learned monitor for effective delegation-scope expansion."""
from __future__ import annotations
import json,math
from pathlib import Path

FEATURES=("task_environment_similarity","capability_overlap","goal_progress_change","action_transition_delta","environment_reference_recency","environment_dependency_chain")

def sigmoid(value):
 value=max(-30.0,min(30.0,value));return 1/(1+math.exp(-value))

class DelegationScopeMonitor:
 def __init__(self,weights,intercept,means,scales,threshold=.5):self.weights=weights;self.intercept=intercept;self.means=means;self.scales=scales;self.threshold=threshold
 def score_features(self,features):
  values=[(float(features[name])-self.means[i])/self.scales[i] for i,name in enumerate(FEATURES)];return sigmoid(self.intercept+sum(w*x for w,x in zip(self.weights,values)))
 def predict_features(self,features):return "SCOPE_EXPANDED" if self.score_features(features)>=self.threshold else "NO_EXPANSION"
 def save(self,path):
  Path(path).write_text(json.dumps({"model":"DelegationScopeMonitor","version":"pilot-v1","features":list(FEATURES),"weights":self.weights,"intercept":self.intercept,"means":self.means,"scales":self.scales,"threshold":self.threshold,"target":"observable INTEGRATED-or-ACTED state","deployment_ready":False},indent=2)+"\n")
 @classmethod
 def load(cls,path):
  value=json.loads(Path(path).read_text());return cls(value["weights"],value["intercept"],value["means"],value["scales"],value["threshold"])

def fit(rows,epochs=1200,learning_rate=.04,l2=.02):
 n=len(FEATURES);means=[sum(float(row["features"][name]) for row in rows)/len(rows) for name in FEATURES];scales=[]
 for i,name in enumerate(FEATURES):
  variance=sum((float(row["features"][name])-means[i])**2 for row in rows)/len(rows);scales.append(max(variance**.5,1e-6))
 data=[([(float(row["features"][name])-means[i])/scales[i] for i,name in enumerate(FEATURES)],int(row["target"])) for row in rows];positives=sum(y for _,y in data);positive_weight=(len(data)-positives)/max(1,positives);weights=[0.0]*n;intercept=0.0
 for _ in range(epochs):
  gw=[0.0]*n;gb=0.0;total=0.0
  for x,y in data:
   importance=positive_weight if y else 1.0;error=(sigmoid(intercept+sum(a*b for a,b in zip(weights,x)))-y)*importance;total+=importance;gb+=error
   for i in range(n):gw[i]+=error*x[i]
  intercept-=learning_rate*gb/total
  for i in range(n):weights[i]-=learning_rate*(gw[i]/total+l2*weights[i])
 return DelegationScopeMonitor(weights,intercept,means,scales)

