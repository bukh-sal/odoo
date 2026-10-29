"""Collect project-owned generated values privately; emit fingerprints/counts only."""
from datetime import datetime,timezone
import base64
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner,is_credential_file

FIELDS={'password','db_password','admin_passwd','client_secret','access_token','refresh_token','api_key','token','service_token','csrf_token','session_id','authorization'}
JSON_NAMES={'fixtures.json','state.json','credentials.json','tokens.json','session.json','service-token.json','log-canaries.json'}


def main():
    assert not LOCAL.exists();protect_directory(LOCAL);OUTPUT.mkdir(exist_ok=True);values={};projects=set();private_logs=[];sources=[]
    def add(label,value):
        if isinstance(value,str):value=value.strip().encode()
        if not isinstance(value,bytes) or len(value)<16 or len(value)>16384 or value.startswith(b'sha256:'):return
        if value.startswith(b'Bearer '):value=value[7:]
        values[label]=value
    def visit(obj,label,canary=False):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k=='project' and isinstance(v,str) and re.fullmatch('mp-r0-[a-z0-9]+|mp-r0-r1[a-z0-9]+',v):projects.add(v)
                if isinstance(v,str) and (k.lower() in FIELDS or canary):add(label+'/'+k,v)
                elif isinstance(v,(dict,list)):visit(v,label+'/'+k,canary)
        elif isinstance(obj,list):
            for i,v in enumerate(obj):visit(v,label+'/'+str(i),canary)
    for folder in (ROOT/'.local').iterdir():
        if not folder.is_dir() or folder==LOCAL or folder.name in ('worktrees','regressions'):continue
        if folder.name not in ('r0','r1','g1','g2','g5','operator') and not folder.name.startswith('g5-'):continue
        for parent,dirs,files in os.walk(folder):
            dirs[:]=[n for n in dirs if n not in ('.git','.venv','node_modules','__pycache__','blobs','staging','worktrees') and not (Path(parent)/n).is_symlink() and not (Path(parent)/n).is_junction()]
            for name in files:
                p=Path(parent)/name
                if p.is_symlink() or p.stat().st_size>4*1024*1024:continue
                label=p.relative_to(ROOT).as_posix();lower=name.lower()
                if p.suffix in ('.log','.stderr','.stdout') or lower.endswith(('-stderr','-stdout')):private_logs.append(label)
                if ('password' in lower or lower in ('service-token','bearer-token')) and is_credential_file(name,p.read_bytes()):
                    add(label,p.read_bytes().strip());sources.append(label)
                if lower in JSON_NAMES or 'credential' in lower and p.suffix=='.json':
                    try:visit(json.loads(p.read_text(encoding='utf8')),label,lower=='log-canaries.json')
                    except (ValueError,UnicodeError):pass
                if lower in ('odoo.conf','odoo_config'):
                    cfg=configparser.ConfigParser()
                    try:cfg.read(p,encoding='utf8')
                    except (ValueError,UnicodeError,configparser.Error):continue
                    if cfg.has_section('options'):
                        for key in ('db_password','admin_passwd'):add(label+'/'+key,cfg['options'].get(key,''))
    # Read only explicitly named disposable DB servers belonging to the project.
    rows=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.service=db','--format','{{json .}}']).splitlines();dbs=[]
    for raw in rows:
        item=json.loads(raw);labels=dict(v.split('=',1) for v in item['Labels'].split(',') if '=' in v);project=labels.get('com.docker.compose.project')
        if project not in projects:continue
        cid=item['ID'];names=json.loads(subprocess.check_output(['docker','exec',cid,'psql','-X','-qAt','-U','postgres','-d','postgres','-c',"SELECT COALESCE(jsonb_agg(datname),'[]') FROM pg_database WHERE NOT datistemplate;"],timeout=15))
        for database in names:
            if not re.fullmatch('mp_disposable_r0_[a-z0-9_]{1,45}',database):continue
            probe=subprocess.check_output(['docker','exec',cid,'psql','-X','-qAt','-U','postgres','-d',database,'-c',"SELECT to_regclass('public.ir_config_parameter') IS NOT NULL;"],timeout=15).strip()
            if probe!=b't':continue
            statement="BEGIN READ ONLY; SELECT COALESCE(jsonb_object_agg(key,value),'{}'::jsonb) FROM ir_config_parameter WHERE key='database.secret' OR key ~ '(^|[._])(password|secret|token)$'; ROLLBACK;"
            settings=json.loads(subprocess.check_output(['docker','exec',cid,'psql','-X','-qAt','-U','postgres','-d',database,'-c',statement],timeout=15))
            for key,value in settings.items():add('database/'+project+'/'+database+'/'+key,value)
            dbs.append(dict(project=project,database=database,read_only=True))
    http=ROOT/'.local/g5-httpsecurity/state.json'
    if http.exists():
        state=json.loads(http.read_text(encoding='utf8'));edge=next(r['container_id'] for r in state['containers'] if r['purpose']=='production-edge')
        key=subprocess.check_output(['docker','exec',edge,'cat','/etc/mp-tls/server.key'],timeout=15);add('private-TLS-key/'+state['project'],key)
    key=secrets.token_bytes(32);(LOCAL/'fingerprint-key').write_bytes(key)
    (LOCAL/'known-values.json').write_text(json.dumps({k:base64.b64encode(v).decode() for k,v in values.items()},indent=2)+'\n',encoding='utf8')
    scanner=Scanner(key,values);scanner.write_patterns(LOCAL/'patterns.regex')
    (LOCAL/'scope.json').write_text(json.dumps(dict(projects=sorted(projects),private_logs=private_logs,databases=dbs),indent=2)+'\n',encoding='utf8')
    report=dict(result='collected_private_values_only',utc=datetime.now(timezone.utc).isoformat(),known_sources=len(values),distinct_values=len(set(values.values())),encoded_patterns=len(scanner.patterns),project_count=len(projects),databases_read_only=len(dbs),private_log_files=len(private_logs),fingerprints=sorted({scanner.fingerprint(v) for v in values.values()}),limits=['Values and scan patterns exist only in owner-protected .local/g5-secret-scan; no credential value or snippet is emitted.','Current/retained owned disposable DB settings are read only; no credential rotation or native operation.'])
    (OUTPUT/'collection.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({k:report[k] for k in ['result','known_sources','distinct_values','encoded_patterns','project_count','databases_read_only','private_log_files']}))


if __name__=='__main__':main()
