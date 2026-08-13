"""Real-model isolated runners for Delegation Bench v1."""
from __future__ import annotations
import argparse,json,os,re,shlex,subprocess,time,urllib.error,urllib.request
from pathlib import Path
from datetime import datetime,timezone
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
from delegation_bench_v1_common import SYSTEM_PROMPTS,TOOL_SCHEMAS,PRIMITIVE_CAPABILITY,file_hashes,sha

class API:
 def __init__(self,model,seed):self.model=model;self.seed=seed;self.key=os.environ.get('OPENAI_API_KEY');self.url='https://api.openai.com/v1/chat/completions'
 def call(self,messages):
  if not self.key:raise RuntimeError('real model credentials unavailable: OPENAI_API_KEY is not configured')
  payload={'model':self.model,'messages':messages,'seed':self.seed,'response_format':{'type':'json_object'}};req=urllib.request.Request(self.url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':f'Bearer {self.key}'},method='POST')
  for attempt in range(5):
   try:
    with urllib.request.urlopen(req,timeout=180) as response:value=json.loads(response.read())['choices'][0]['message']['content']
    break
   except urllib.error.HTTPError as error:
    if attempt==4 or error.code<500:raise RuntimeError(f'API HTTP {error.code}: {error.read().decode(errors="replace")[:500]}') from error
   except (urllib.error.URLError,TimeoutError):
    if attempt==4:raise
   time.sleep(2**attempt)
  match=re.search(r'\{.*\}',value,re.S)
  if not match:raise RuntimeError('model returned no JSON tool action')
  return json.loads(match.group())
def parser():
 p=argparse.ArgumentParser();p.add_argument('--task',required=True);p.add_argument('--environment',type=Path,required=True);p.add_argument('--session-spec',type=Path,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--model',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-steps',type=int,default=12);return p
def snapshot(path):return sha(file_hashes(path))
def activate_coding(root,payload): (root/'runtime_notice.txt').write_text(payload+'\n')
def coding_action(root,request):
 tool=request.get('tool','');arg=request.get('path','.')
 if tool=='list_files':return '\n'.join(sorted(str(x.relative_to(root)) for x in root.rglob('*') if x.is_file()))
 if tool=='read_file':return (root/arg).resolve().read_text(errors='replace')
 if tool=='edit_file':(root/arg).resolve().write_text(request.get('content',''));return 'local file updated'
 if tool=='run_command':
  cmd=request.get('command','');argv=shlex.split(cmd);allowed=argv and (argv[0]=='pytest' or argv[:3]==['python3','-m','pytest'])
  if not allowed:return 'policy blocked: only local pytest is permitted'
  done=subprocess.run(argv,cwd=root,text=True,capture_output=True,timeout=120);return done.stdout+done.stderr+f'\n[exit_code={done.returncode}]'
 if tool=='finish':return request.get('summary','finished')
 return 'tool error: unknown action'
def run(paradigm):
 a=parser().parse_args();spec=json.loads(a.session_spec.read_text());scheduled=int(spec['scheduled_exposure_step']);payload=spec['payload_at_boundary'];second=spec.get('second_payload');api=API(a.model,a.seed);messages=[{'role':'system','content':SYSTEM_PROMPTS[paradigm]+' Tools: '+json.dumps(TOOL_SCHEMAS[paradigm])},{'role':'user','content':'Task:\n'+a.task}];steps=[];actual=None;finished=False
 site=json.loads((a.environment/'site.json').read_text()) if paradigm=='web' else None;ui=json.loads((a.environment/'ui_state.json').read_text()) if paradigm=='gui' else None;current='home';state={}
 for step in range(1,a.max_steps+1):
  active=step>=scheduled;active_payload=second if second and step>scheduled else payload
  if paradigm=='coding' and active:activate_coding(a.environment,active_payload)
  request=api.call(messages);tool=request.get('tool','');arguments={k:v for k,v in request.items() if k!='tool'}
  if paradigm=='coding':observation=coding_action(a.environment,request);source='runtime_boundary' if active and tool=='read_file' and request.get('path')=='runtime_notice.txt' else ('TEST_OUTPUT' if tool=='run_command' else 'tool_output')
  elif paradigm=='web':
   if tool in {'open_page','click'}:current=request.get('page',request.get('target',current));page=dict(site['pages'].get(current,{'error':'not found'}));page['notice']=active_payload if active else page.get('notice','');observation=json.dumps({'page':current,**page},sort_keys=True);source='webpage'
   elif tool=='fill_form':state['draft']=request.get('fields',{});observation='form staged in isolated session';source='form'
   elif tool=='submit_form':state['mock_submission']=True;observation='mock form submitted';source='mock_external_effect'
   elif tool=='finish':observation=request.get('summary','finished');source='web_tool'
   else:observation='tool error: unknown action';source='web_tool'
  else:
   if tool=='inspect_screen':observation=json.dumps({**ui,'notice':active_payload if active else ui.get('notice','')},sort_keys=True);source='gui_screen'
   elif tool in {'tap','type_text'}:state[tool]=arguments;observation='mock interface state updated locally';source='gui_local'
   elif tool=='change_permission':state['permission']=arguments;observation='mock permission changed';source='gui_persistent'
   elif tool=='commit':state['mock_commit']=arguments;observation='mock external-effect action committed in isolated session';source='mock_external_effect'
   elif tool=='finish':observation=request.get('summary','finished');source='gui_tool'
   else:observation='tool error: unknown action';source='gui_tool'
  # The scheduled environment event is attached to the next real tool result.
  # A finish action receives no new environment observation and is therefore an
  # auditable early termination rather than a fabricated exposure.
  if active and tool!='finish' and active_payload not in observation:
   observation+='\nBoundary environment observation: '+active_payload;source=source+'+runtime_boundary'
  if active and active_payload in observation and actual is None:actual=step
  visible_snapshot=snapshot(a.environment) if paradigm=='coding' else sha({'fixture':snapshot(a.environment),'active_boundary_payload':active_payload if active else None,'session_state':state,'current_surface':current if paradigm=='web' else ui.get('screen')})
  action=tool+' '+str(next(iter(arguments.values()),''));steps.append({'step':step,'tool':tool,'action':action.strip(),'arguments':json.dumps(arguments,sort_keys=True),'observation':observation,'observation_source':source,'capability_state':PRIMITIVE_CAPABILITY[paradigm].get(tool,'A0_OBSERVE'),'environment_snapshot_hash':visible_snapshot,'timestamp':datetime.now(timezone.utc).isoformat()})
  messages.extend([{'role':'assistant','content':json.dumps(request,sort_keys=True)},{'role':'user','content':'Tool observation:\n'+observation}]);finished=tool=='finish'
  if finished:break
 result={'task':a.task,'seed':a.seed,'model':a.model,'scheduled_exposure_step':scheduled,'actual_exposure_step':actual,'steps':steps,'finished':finished,'early_termination':finished and actual is None,'mock_session_state':state};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
