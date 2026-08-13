"""Authorization-blind structured action and shell-command normalizer."""
from __future__ import annotations
import json,re,shlex
from pathlib import Path
URL=re.compile(r'https?://([^/:\s"\']+)',re.I)
SEPARATORS=re.compile(r'(?:&&|\|\||;|(?<!\|)\|(?!\|))')
REDIR=re.compile(r'(?:^|\s)(?:>>?|<<?)\s*([^\s;&|]+)')
def _tokens(text):
 try:return shlex.split(text,posix=True)
 except ValueError:return text.split()
def _split_shell(command):
 # Preserve substitutions/heredoc bodies as opaque subactions while exposing the outer command.
 parts=[x.strip() for x in SEPARATORS.split(command.replace('\n',' ; ')) if x.strip()]
 return parts or [command]
def _paths(tokens):
 out=[]
 for i,t in enumerate(tokens):
  clean=t.strip('"\'')
  if i and (clean.startswith(('.', '/')) or '/' in clean or re.search(r'\.(?:py|sh|json|ya?ml|toml|ini|cfg|txt|env|pem|key)$',clean,re.I)):out.append(clean)
 return list(dict.fromkeys(out))
def normalize_action(record):
 args=record.tool_args or {};tool=record.tool_name or '';command=str(args.get('command') or record.raw_command or '')
 if tool in {'read_file','search_text','list_files'}:
  path=str(args.get('path') or '.');return {'subactions':[{'verb':tool,'operation':'read','paths':[path],'hosts':[],'arguments':[path]}]}
 if tool=='edit_file':
  path=str(args.get('path') or '');return {'subactions':[{'verb':tool,'operation':'write','paths':[path] if path else [],'hosts':[],'arguments':[path]}]}
 if tool=='finish':return {'subactions':[{'verb':'finish','operation':'none','paths':[],'hosts':[],'arguments':[]}]}
 if tool and tool!='run_command':return {'subactions':[{'verb':tool,'operation':'tool','paths':list(record.target_paths),'hosts':list(record.target_hosts),'arguments':[]}]}
 subs=[]
 for part in _split_shell(command):
  toks=_tokens(part);verb=Path(toks[0]).name.lower() if toks else '';hosts=URL.findall(part);paths=_paths(toks)
  paths += [m.strip('"\'') for m in REDIR.findall(part)]
  op='execute'
  if verb in {'cat','head','tail','less','grep','rg','find','ls','sed','awk'}:op='read'
  elif verb in {'cp','mv','rm','mkdir','touch','chmod','tee'}:op='write'
  elif verb in {'pytest','unittest'} or toks[:3] in (['python','-m','pytest'],['python3','-m','pytest']):op='test'
  elif verb in {'pip','pip3','uv','poetry','npm','yarn'} and any(x in toks for x in ('install','add','i')):op='install'
  elif verb=='git' and len(toks)>1:op='git_'+toks[1]
  if '$(' in part or '<<' in part:op='opaque' if verb in {'python','python3','bash','sh'} else op
  if REDIR.search(part) and re.search(r'(?:^|\s)>>?\s*',part):op='write'
  subs.append({'verb':verb,'operation':op,'paths':list(dict.fromkeys(paths)),'hosts':list(dict.fromkeys(hosts)),'arguments':toks[1:]})
 return {'subactions':subs or [{'verb':'','operation':'none','paths':[],'hosts':[],'arguments':[]}]}
