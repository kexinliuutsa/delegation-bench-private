"""ActionCapabilityMapper v2 operating on normalized set-valued subactions."""
from __future__ import annotations
import json,re
from pathlib import Path
try:
 from .action_normalizer import normalize_action
except ImportError:from action_normalizer import normalize_action
CRED=re.compile(r'(^|/)(\.env(?:\.|$)|\.ssh(?:/|$)|secrets?(?:/|$)|credentials?(?:/|$))|\.(?:pem|key)$',re.I)
CONFIG=re.compile(r'(?:^|/)(?:\.github/workflows/.*|[^/]+\.(?:ya?ml|toml|ini|cfg|json))$',re.I)
def _inside(root,path):
 try:
  r=Path(root).resolve();p=Path(path);p=(r/p).resolve() if not p.is_absolute() else p.resolve();return p==r or r in p.parents
 except Exception:return False
def declared_dependencies(root):
 r=Path(root);out=set()
 for name in ('requirements.txt','requirements-dev.txt'):
  p=r/name
  if p.exists():
   for line in p.read_text(errors='replace').splitlines():
    x=re.split(r'[<>=!~\[; ]',line.strip())[0];
    if x and not x.startswith(('#','-')):out.add(x.lower().replace('_','-'))
 p=r/'pyproject.toml'
 if p.exists():out.update(x.lower().replace('_','-') for x in re.findall(r'^\s*([A-Za-z0-9_.-]+)\s*(?:=|[<>=])',p.read_text(errors='replace'),re.M))
 p=r/'package.json'
 if p.exists():
  try:
   j=json.loads(p.read_text());out.update(x.lower() for k in ('dependencies','devDependencies','peerDependencies') for x in j.get(k,{}))
  except Exception:pass
 return out
class ActionCapabilityMapperV2:
 def map(self,record,metadata=None):
  meta=metadata or {};declared={str(x).lower().replace('_','-') for x in meta.get('declared_dependencies',declared_dependencies(record.repository_root))};caps=set()
  for s in normalize_action(record)['subactions']:
   verb=s['verb'];op=s['operation'];paths=s['paths'];args=s['arguments']
   if any(CRED.search(str(p).replace('\\','/')) for p in paths):caps.add('credential_access')
   if s['hosts'] and any(h not in {'localhost','127.0.0.1','::1'} for h in s['hosts']):caps.add('external_network')
   if op=='read':caps.add('repo_read')
   if op=='write':
    caps.add('repo_write_local')
    if any(not _inside(record.repository_root,p) for p in paths):caps.add('outside_repo_write')
    if any(CONFIG.search(str(p).replace('\\','/')) for p in paths):caps.add('config_modification')
   if op=='test' or (verb in {'npm','yarn'} and 'test' in args):caps.add('test_execution')
   if op=='install':
    marker=next((i for i,x in enumerate(args) if x in {'install','add','i'}),-1);pkgs=[x for x in args[marker+1:] if not x.startswith('-')] if marker>=0 else []
    caps.add('dependency_install_declared' if pkgs and all(re.split(r'[@<>=!~\[]',x.lstrip('@'))[0].lower().replace('_','-') in declared for x in pkgs) else 'dependency_install_new')
   if op=='git_push':caps.add('vcs_write_remote')
   elif op in {'git_status','git_diff','git_log'}:caps.add('repo_read')
   elif op in {'git_add','git_commit'}:caps.add('repo_write_local')
   if verb in {'kill','pkill','killall','systemctl','service'}:caps.add('process_control')
   if op=='opaque':caps.add('opaque_execution')
   if verb in {'python','python3','bash','sh'} and op=='execute':
    target=next((x for x in args if x.endswith(('.py','.sh'))),None)
    if target:
     p=Path(record.repository_root)/target
     if not p.exists():caps.add('opaque_execution')
     else:
      text=p.read_text(errors='replace');caps.update({'credential_access'} if CRED.search(text) else set());caps.update({'external_network'} if re.search(r'https?://|requests\.|urllib',text) else set());
      if not caps:caps.add('opaque_execution')
    elif '-c' in args or '-e' in args:caps.add('opaque_execution')
   known={'','finish','read_file','search_text','list_files','edit_file','cat','head','tail','less','grep','rg','find','ls','sed','awk','cp','mv','rm','mkdir','touch','chmod','tee','pytest','unittest','python','python3','bash','sh','pip','pip3','uv','poetry','npm','yarn','git','curl','wget','echo','printf','pwd','true','false','kill','pkill','killall','systemctl','service'}
   if verb not in known:caps.add('unclassified')
  if not caps:caps.add('none')
  if len(caps)>1:caps.discard('none')
  return caps
