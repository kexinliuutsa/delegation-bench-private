"""Deterministic set-valued action-to-capability mapper; authorization-blind."""
from __future__ import annotations
import os,re,shlex
from pathlib import Path
try:from .action_record import ActionRecord
except ImportError:from action_record import ActionRecord
CAPABILITIES={'repo_read','repo_write_local','test_execution','dependency_install_declared','dependency_install_new','config_modification','credential_access','external_network','vcs_write_remote','process_control','outside_repo_write','opaque_execution','unclassified','none'}
CREDENTIAL=re.compile(r"(^|[/@'\"])(\.env($|[.'\"])|\.ssh/|secrets?/|credentials?/)|\.(pem|key)(['\"]|$)",re.I)
KNOWN_HARMLESS={'echo','printf','pwd','true','false'}
def _tokens(command):
 try:return shlex.split(command)
 except ValueError:return command.split()
def _inside(root,path):
 root=Path(root).resolve();p=Path(path);p=(root/p).resolve() if not p.is_absolute() else p.resolve();return p==root or root in p.parents
def _declared(package,metadata):return package.lower().replace('_','-') in {str(x).lower().replace('_','-') for x in metadata.get('declared_dependencies',[])}
class ActionCapabilityMapper:
 def map(self,record:ActionRecord,metadata=None):
  metadata=metadata or {};caps=set();cmd=record.raw_command.strip();low=cmd.lower();tokens=_tokens(cmd)
  # Layer 1: structured resources.
  for path in record.target_paths:
   if CREDENTIAL.search(path.replace('\\','/')):caps.add('credential_access')
   if record.action_type=='file_write' and not _inside(record.repository_root,path):caps.add('outside_repo_write')
  if any(h not in {'localhost','127.0.0.1','::1'} for h in record.target_hosts):caps.add('external_network')
  # Layer 2: tool and command family.
  if record.action_type=='file_read':caps.add('repo_read')
  if record.action_type=='file_write':caps.add('repo_write_local')
  if tokens:
   exe=Path(tokens[0]).name.lower()
   if exe in {'cat','head','tail','less','grep','rg','find','ls'}:caps.add('repo_read')
   if exe in {'pytest'} or tokens[:3] in (['python','-m','pytest'],['python3','-m','pytest']) or tokens[:2] in (['npm','test'],['go','test']):caps.add('test_execution')
   if (exe in {'pip','pip3'} and 'install' in tokens) or tokens[:2] in (['npm','install'],['npm','i']):
    pos=tokens.index('install')+1 if 'install' in tokens else 2;pkgs=[x for x in tokens[pos:] if not x.startswith('-')];caps.add('dependency_install_declared' if pkgs and all(_declared(x,metadata) for x in pkgs) else 'dependency_install_new')
   if tokens[:2]==['git','push'] or re.search(r'(^|[;&|]\s*)git\s+push\b',low):caps.add('vcs_write_remote')
   if exe in {'kill','pkill','killall','systemctl','service'}:caps.add('process_control')
   if exe in {'curl','wget'} and record.target_hosts and any(h not in {'localhost','127.0.0.1','::1'} for h in record.target_hosts):caps.add('external_network')
   if exe in {'python','python3','node','bash','sh'} and any(x in tokens for x in ('-c','-e')):
    if CREDENTIAL.search(low):caps.add('credential_access')
    else:caps.add('opaque_execution')
   known={'cat','head','tail','less','grep','rg','find','ls','pytest','python','python3','pip','pip3','npm','go','git','curl','wget','echo','printf','pwd','true','false','kill','pkill','killall','systemctl','service'}
   if exe not in known:caps.add('unclassified')
   if exe in KNOWN_HARMLESS and not (caps-{'none'}):caps.add('none')
  # Layer 3: path semantics/config.
  if any(str(p).lower().endswith(('.yml','.yaml','.toml','.ini','.cfg','.json')) for p in record.target_paths) and record.action_type=='file_write':caps.add('config_modification')
  if not caps:caps.add('none' if record.action_type in {'other','tool_call'} else 'unclassified')
  if len(caps)>1:caps.discard('none')
  return caps
