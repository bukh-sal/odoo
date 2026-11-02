"""Continue against the healthy exact server on its internal TCP listener."""
import json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core21-fresh-registry-01'
state=json.loads((PRIVATE/'state.json').read_text());assert state['state']=='native_http_checks_running'
def call(label,args,raw=None,timeout=120):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=raw,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect exact '+label+' and live server; no recreation'
 return (PRIVATE/(label+'.stdout')).read_bytes()
info=json.loads(call('http-internal-continuation-inspect',['docker','inspect','--type','container',state['http_container_id']]))[0]
assert info['State']['Running'] and info['Image']==state['image_id'] and info['Config']['Labels']['com.modular.disposable']==state['project']
original=(OUT/'fresh_http.py').read_text();start=original.index("base='http://127.0.0.1:'");end=original.index("phase('native_http_checks_passed_stopping_temporary_server')",start)
code="import hashlib,html.parser,http.cookiejar,json,re,sys,time,urllib.error,urllib.parse,urllib.request\nd=json.load(sys.stdin);state={'database':d['database']};password=d['password'];port=8069\n"+original[start:end]
code+="\nprint('MP_NATIVE_HTTP='+json.dumps(dict(uid=session['result']['uid'],login_status=login_status,login_page_sha256=login_page_sha,assets=assets)))\n"
payload=json.dumps(dict(database=state['database'],password=(PRIVATE/'admin-password').read_text().strip())).encode()
raw=call('http-internal-client',['docker','exec','-i',state['http_container_id'],'/venv/bin/python','-B','-c',code],payload)
rows=[json.loads(line.split('MP_NATIVE_HTTP=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_NATIVE_HTTP=')];assert len(rows)==1 and rows[0]['uid']==2
call('http-log-archive',['docker','exec',state['http_container_id'],'cat','/var/lib/modular/http-probe.log'])
call('http-stop',['docker','stop','--time','20',state['http_container_id']])
terminal=json.loads(call('http-terminal-inspect',['docker','inspect','--type','container',state['http_container_id']]))[0]
assert terminal['Config']['Labels']['com.modular.disposable']==state['project'] and terminal['State']['Status']=='exited'
call('http-retire',['docker','rm',state['http_container_id']])
absent=subprocess.run(['docker','inspect','--type','container',state['http_container_id']],capture_output=True,timeout=30);assert absent.returncode!=0 and b'no such' in absent.stderr.lower()
state['state']='fresh_core_native_login_assets_passed_http_server_retired';(PRIVATE/'state.json').write_text(json.dumps(state,indent=2)+'\n')
report=dict(result='passed_fresh_native_login_session_and_assets',database=state['database'],image_id=state['image_id'],**rows[0],nondefault_private_password=True,csrf_form_token_used=True,
 client_location='Actual HTTP TCP127.0.0.1:8069 within the existing temporary native server container',temporary_http_server_removed=True,
 limits=['Initial host18090 attempt refused: Docker published port list empty on existing internal network; server remained healthy and was not restarted.',
 'Native bootstrap entrypoint only; not production/proxy/startup-guard/platform-site/plugin/lifecycle/recovery/full security qualification.',
 'No UI code or Canvas changes; real native login/session/CSS/JS bytes only.'])
with (OUT/'fresh-http.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],uid=2,assets=len(rows[0]['assets']),temporary_server_removed=True)))
