#!/usr/bin/env python3
"""Adapter from a real SWE-agent-compatible native log to AuthoritySourceBench."""
from __future__ import annotations
import argparse,json,os,shlex,shutil,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path

def infer_tool(action):
 try:tokens=shlex.split(action)
 except ValueError:tokens=action.split()
 return (tokens[0] if tokens else 'unknown'),' '.join(tokens[1:])
def source_channel(action,provided):
 lowered=action.lower().strip()
 if (lowered.startswith(('open readme','cat readme','read_file readme','sed ')) and 'readme' in lowered):return 'README'
 if 'pytest' in lowered:return 'TEST_OUTPUT'
 return provided or 'tool_output'
def native_steps(data):
 values=data.get('trajectory',data.get('steps',[]));output=[]
 for item in values:
  if not isinstance(item,dict):continue
  action=item.get('action',item.get('command',''));observation=item.get('observation',item.get('output',''))
  if not action:continue
  tool,args=infer_tool(action);provided=item.get('source_channel',item.get('observation_source','tool_output'));output.append({'action':action,'tool':item.get('tool',tool),'arguments':item.get('arguments',args),'observation':observation,'source_channel':source_channel(action,provided),'thought':item.get('thought',''),'timestamp':item.get('timestamp',datetime.now(timezone.utc).isoformat())})
 return output
def main():
 p=argparse.ArgumentParser();p.add_argument('--task',required=True);p.add_argument('--repository',type=Path,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--model',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pair-id',required=True);p.add_argument('--condition',choices=('control','treatment'),required=True);p.add_argument('--native-command',default=os.environ.get('SWE_AGENT_COMMAND'));p.add_argument('--native-cwd',type=Path,help='Directory used to resolve the native runner executable');a=p.parse_args()
 if not a.native_command:raise SystemExit('no real runner provided: set --native-command or SWE_AGENT_COMMAND')
 native_path=Path(tempfile.mkdtemp(prefix='swe_agent_native_'))/'trajectory.json';command=a.native_command.format(task=shlex.quote(a.task),repo=shlex.quote(str(a.repository)),seed=a.seed,model=shlex.quote(a.model),output=shlex.quote(str(native_path)));completed=subprocess.run(command,shell=True,cwd=a.native_cwd or a.repository,text=True,capture_output=True)
 if completed.returncode:raise SystemExit(f'native SWE-agent failed ({completed.returncode}): {completed.stderr[-2000:]}')
 if not native_path.exists():raise SystemExit('native runner succeeded but produced no trajectory log')
 raw=json.loads(native_path.read_text());steps=native_steps(raw)
 if not steps:raise SystemExit('native trajectory contains no parseable real agent actions')
 encoded=[]
 for index,step in enumerate(steps,1):
  thought=step['thought'];encoded.append({key:value for key,value in step.items() if key!='thought'}|{'step':index,'native_thought':thought})
 result={'pair_id':a.pair_id,'condition':a.condition,'task':a.task,'repository':str(a.repository),'seed':a.seed,'model':a.model,'steps':encoded};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
