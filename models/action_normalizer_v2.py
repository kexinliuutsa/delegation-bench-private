"""Normalizer v2: deterministic structured-schema canonicalization only."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from .action_record import ActionRecord
from .action_normalizer_v1_experiment77 import normalize_action as _v1

ALIASES=('path','paths','file','filename','command','cmd','arguments')
KNOWN={'read_file','edit_file','run_command','search_text','list_files','finish'}

def _same(a,b): return a == b or str(a) == str(b)
def canonicalize_fields(value):
 d=dict(value if isinstance(value,dict) else {})
 nested=d.get('tool_args') if isinstance(d.get('tool_args'),dict) else {}
 tool=d.get('tool_name') or d.get('tool') or nested.get('tool_name')
 if not tool or tool not in KNOWN:return {'status':'ABSTAIN','reason':'unknown_or_missing_tool','tool_name':tool,'tool_args':{}}
 out={k:v for k,v in nested.items() if k!='tool_name'}
 for key in ALIASES:
  vals=[d[k] for k in (key,) if k in d and d[k] is not None]
  if key=='command' and d.get('cmd') is not None: vals.append(d['cmd'])
  if key=='path':
   for alias in ('file','filename'):
    if d.get(alias) is not None: vals.append(d[alias])
  if key in out: vals.append(out[key])
  if vals and any(not _same(vals[0],x) for x in vals[1:]):return {'status':'ABSTAIN','reason':'conflicting_duplicate_fields','tool_name':tool,'tool_args':{}}
  if vals:out[key]=vals[0]
 if tool in {'read_file','edit_file'} and 'path' not in out:return {'status':'ABSTAIN','reason':'missing_path','tool_name':tool,'tool_args':{}}
 if tool=='run_command' and not (out.get('command') or out.get('arguments')):return {'status':'ABSTAIN','reason':'missing_command','tool_name':tool,'tool_args':{}}
 if tool=='run_command' and 'command' not in out and isinstance(out.get('arguments'),str):out['command']=out['arguments']
 return {'status':'RESOLVED','reason':None,'tool_name':tool,'tool_args':out}

def record_from_structured(value,step_index=0,repository_root='.'):
 c=canonicalize_fields(value)
 if c['status']!='RESOLVED':return None,c
 tool,args=c['tool_name'],c['tool_args']; path=args.get('path');cmd=str(args.get('command') or '')
 typ={'read_file':'file_read','edit_file':'file_write','run_command':'shell_command'}.get(tool,'tool_call')
 return ActionRecord(step_index,typ,cmd,tool,args,[str(path)] if path else [],[],str(Path(repository_root).resolve())),c

def normalize_action(record):
 if isinstance(record,dict):
  rec,status=record_from_structured(record)
  if rec is None:return {'subactions':[{'verb':'','operation':'abstain','paths':[],'hosts':[],'arguments':[]}],**status}
  return {**_v1(rec),'status':'RESOLVED','reason':None}
 # Repair records whose original proposal was stored in tool_args as a top-level schema.
 if not record.tool_name and isinstance(record.tool_args,dict) and record.tool_args.get('tool_name'):
  rec,status=record_from_structured(record.tool_args,record.step_index,record.repository_root)
  if rec is None:return {'subactions':[{'verb':'','operation':'abstain','paths':[],'hosts':[],'arguments':[]}],**status}
  return {**_v1(rec),'status':'RESOLVED','reason':None}
 return {**_v1(record),'status':'RESOLVED','reason':None}
