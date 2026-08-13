#!/usr/bin/env python3
"""v1.3 runner: historical semantics plus append-only pre-dispatch observability."""
from __future__ import annotations
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runners'));sys.path.insert(0,str(ROOT/'experiments'))
from v1_agent_common import API,activate_coding,snapshot
from delegation_bench_v1_common import SYSTEM_PROMPTS,TOOL_SCHEMAS,PRIMITIVE_CAPABILITY,sha
def append(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a') as f:f.write(json.dumps(value,sort_keys=True)+'\n')
def event(path,name,seq,**kw):append(path,{'timestamp':datetime.now(timezone.utc).isoformat(),'sequence':seq,'event':name,**kw})
def persist_proposal(path,ctx,step,proposal):
 append(path,{'timestamp':datetime.now(timezone.utc).isoformat(),**ctx,'step':step,'raw_tool_name':proposal.get('tool') if isinstance(proposal,dict) else None,'raw_tool_arguments':{k:v for k,v in proposal.items() if k!='tool'} if isinstance(proposal,dict) else None,'raw_structured_proposal':proposal,'provider_response_metadata_if_safe':{'api':'openai_chat_completions','response_format':'json_object'}})
def coding_execute(root,request):
 tool=request.get('tool','');arg=request.get('path','.')
 if tool=='list_files':return '\n'.join(sorted(str(x.relative_to(root)) for x in root.rglob('*') if x.is_file()))
 if tool=='read_file':return (root/arg).resolve().read_text(errors='replace')
 if tool=='edit_file':(root/arg).resolve().write_text(request.get('content',''));return 'local file updated'
 if tool=='run_command':
  import shlex,subprocess
  cmd=request.get('command','');argv=shlex.split(cmd);allowed=argv and (argv[0]=='pytest' or argv[:3]==['python3','-m','pytest'])
  if not allowed:return 'policy blocked: only local pytest is permitted'
  d=subprocess.run(argv,cwd=root,text=True,capture_output=True,timeout=120);return d.stdout+d.stderr+f'\n[exit_code={d.returncode}]'
 if tool=='finish':return request.get('summary','finished')
 return 'tool error: unknown action'
def main():
 p=argparse.ArgumentParser();p.add_argument('--paradigm',choices=['coding','web'],required=True);p.add_argument('--task',required=True);p.add_argument('--environment',type=Path,required=True);p.add_argument('--session-spec',type=Path,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--model',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-steps',type=int,default=12);p.add_argument('--pair-id',required=True);p.add_argument('--trajectory-id',required=True);p.add_argument('--condition',required=True);p.add_argument('--raw-log',type=Path,required=True);p.add_argument('--dispatch-log',type=Path,required=True);a=p.parse_args();spec=json.loads(a.session_spec.read_text());scheduled=spec['scheduled_exposure_step'];payload=spec['payload_at_boundary'];api=API(a.model,a.seed);msgs=[{'role':'system','content':SYSTEM_PROMPTS[a.paradigm]+' Tools: '+json.dumps(TOOL_SCHEMAS[a.paradigm])},{'role':'user','content':'Task:\n'+a.task}];ctx={'model':a.model,'pair_id':a.pair_id,'trajectory_id':a.trajectory_id,'condition':a.condition};steps=[];actual=None;finished=False;site=json.loads((a.environment/'site.json').read_text()) if a.paradigm=='web' else None;current='home';state={}
 for step in range(1,a.max_steps+1):
  active=step>=scheduled
  if a.paradigm=='coding' and active:activate_coding(a.environment,payload)
  request=api.call(msgs);seq=1;event(a.dispatch_log,'MODEL_PROPOSAL_RECEIVED',seq,**ctx,step=step);seq+=1
  persist_proposal(a.raw_log,ctx,step,request);event(a.dispatch_log,'RAW_PROPOSAL_PERSISTED',seq,**ctx,step=step);seq+=1
  try:
   event(a.dispatch_log,'NORMALIZATION',seq,**ctx,step=step);seq+=1;tool=request.get('tool','');args={k:v for k,v in request.items() if k!='tool'}
   valid=tool in ({'list_files','read_file','edit_file','run_command','finish'} if a.paradigm=='coding' else {'open_page','click','fill_form','submit_form','finish'});status='VALID_ACTION' if valid else ('NON_ACTION_MESSAGE' if not tool and any(k in request for k in ('message','summary','text')) else 'UNRESOLVED')
   event(a.dispatch_log,'DISPATCH_CLASSIFICATION',seq,**ctx,step=step,dispatch_status=status,normalized_tool=tool,normalized_args=args);seq+=1;event(a.dispatch_log,'EXECUTOR_SELECTION',seq,**ctx,step=step,executor_selected=(a.paradigm+'_executor' if valid else None));seq+=1
   event(a.dispatch_log,'FILESYSTEM/TOOL_EXECUTION',seq,**ctx,step=step)
   if a.paradigm=='coding':obs=coding_execute(a.environment,request);source='runtime_boundary' if active and tool=='read_file' and request.get('path')=='runtime_notice.txt' else ('TEST_OUTPUT' if tool=='run_command' else 'tool_output')
   elif tool in {'open_page','click'}:current=request.get('page',request.get('target',current));page=dict(site['pages'].get(current,{'error':'not found'}));page['notice']=payload if active else page.get('notice','');obs=json.dumps({'page':current,**page},sort_keys=True);source='webpage'
   elif tool=='fill_form':state['draft']=request.get('fields',{});obs='form staged in isolated session';source='form'
   elif tool=='submit_form':state['mock_submission']=True;obs='mock form submitted';source='mock_external_effect'
   elif tool=='finish':obs=request.get('summary','finished');source='web_tool'
   else:obs='tool error: unknown action';source='web_tool'
   append(a.dispatch_log,{'timestamp':datetime.now(timezone.utc).isoformat(),**ctx,'step':step,'dispatch_status':'EXECUTED','normalized_tool':tool,'normalized_args':args,'executor_selected':a.paradigm+'_executor','exception_type':None,'exception_message':None})
  except Exception as exc:
   append(a.dispatch_log,{'timestamp':datetime.now(timezone.utc).isoformat(),**ctx,'step':step,'dispatch_status':'EXECUTION_FAILED','normalized_tool':locals().get('tool'),'normalized_args':locals().get('args'),'executor_selected':a.paradigm+'_executor','exception_type':type(exc).__name__,'exception_message':str(exc)});raise
  if active and tool!='finish' and payload not in obs:obs+='\nBoundary environment observation: '+payload;source+='+runtime_boundary'
  if active and payload in obs and actual is None:actual=step
  action=tool+' '+str(next(iter(args.values()),''));steps.append({'step':step,'tool':tool,'action':action.strip(),'arguments':json.dumps(args,sort_keys=True),'observation':obs,'observation_source':source,'capability_state':PRIMITIVE_CAPABILITY[a.paradigm].get(tool,'A0_OBSERVE'),'environment_snapshot_hash':snapshot(a.environment),'timestamp':datetime.now(timezone.utc).isoformat()});msgs.extend([{'role':'assistant','content':json.dumps(request,sort_keys=True)},{'role':'user','content':'Tool observation:\n'+obs}]);finished=tool=='finish'
  if finished:break
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'task':a.task,'seed':a.seed,'model':a.model,'scheduled_exposure_step':scheduled,'actual_exposure_step':actual,'steps':steps,'finished':finished,'early_termination':finished and actual is None,'mock_session_state':state},indent=2)+'\n')
if __name__=='__main__':main()
