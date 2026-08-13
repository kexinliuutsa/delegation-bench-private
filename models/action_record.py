"""Normalized observable action records for coding-agent trajectories."""
from __future__ import annotations
import json,re,shlex
from dataclasses import asdict,dataclass
from pathlib import Path

@dataclass(frozen=True)
class ActionRecord:
 step_index:int;action_type:str;raw_command:str;tool_name:str|None;tool_args:dict|None;target_paths:list[str];target_hosts:list[str];repository_root:str
 def to_dict(self):return asdict(self)

HOST=re.compile(r"https?://([^/:\s]+)",re.I)
def _tokens(value):
 try:return shlex.split(value)
 except ValueError:return value.split()
def from_coding_step(step,repository_root):
 tool=str(step.get('tool') or '');args=step.get('arguments',{})
 if isinstance(args,str):
  try:args=json.loads(args)
  except Exception:args={}
 action=str(step.get('action',''));cmd=str(args.get('command','')) if tool=='run_command' else action
 typ={'run_command':'shell_command','edit_file':'file_write','read_file':'file_read'}.get(tool,'tool_call' if tool else 'other');paths=[]
 if tool in {'read_file','edit_file','list_files','search_text'} and args.get('path') is not None:paths.append(str(args['path']))
 toks=_tokens(cmd)
 for i,t in enumerate(toks):
  if t in {'cat','head','tail','less','source','-r','--file','-f'} and i+1<len(toks):paths.append(toks[i+1])
  if t.startswith(('./','../','/')) or any(x in t.lower() for x in ('.env','.pem','.key','.ssh/','secrets/','credentials')):paths.append(t.strip('"\''))
 return ActionRecord(int(step.get('step',step.get('step_index',0))),typ,cmd,tool or None,args or None,list(dict.fromkeys(paths)),list(dict.fromkeys(HOST.findall(cmd))),str(Path(repository_root).resolve()))
