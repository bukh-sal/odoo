"""Explicit local operator bootstrap of NEW copied qualification site only."""
import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-production-profile-01';SOURCE=ROOT/'.local/g7-fresh-release-01/target21'
s=json.loads((LOCAL/'state.json').read_text());target=json.loads((LOCAL/'operator/target.json').read_text());prior=json.loads((SOURCE/'operator/target.json').read_text())
assert s['phase']=='profiles_started_ready' and target['project']!=prior['project'] and target['sites'][0]['database']!=prior['sites'][0]['database'] and target['sites'][0]['site_id']!=prior['sites'][0]['site_id']
request=dict(new_site=target['sites'][0]['site_id'],old_site=prior['sites'][0]['site_id'],new_release=__import__('hashlib').sha256(json.dumps(target['published_release'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
import sys;sys.path.insert(0,str(ROOT/'packages/platform_sdk'));from modular_platform.plans import data_digest
request['new_release']=data_digest(target['published_release']);request['old_release']=data_digest(prior['published_release']);request['database']=s['active_db']
(LOCAL/'dispatch-bootstrap-request.json').write_text(json.dumps(request,indent=2))
code="""import configparser,json,sys,psycopg2
sys.path.insert(0,'/opt/modular/packages/platform_sdk')
from modular_platform.durable import set_control
v=json.load(sys.stdin);c=configparser.ConfigParser();c.read('/run/secrets/odoo_config');o=c['options'];assert o['db_name']==v['database']
conn=psycopg2.connect(host=o['db_host'],dbname=o['db_name'],user=o['db_user'],password=o['db_password'])
try:
 with conn:
  with conn.cursor() as cr:
   cr.execute('SELECT site_id,release_digest,state,generation FROM mp_dispatch_control ORDER BY site_id');before=cr.fetchall();assert len(before)==1 and before[0][0]==v['old_site'] and before[0][1]==v['old_release'] and before[0][2]=='enabled'
   cr.execute("SELECT count(*) FROM mp_job WHERE state IN ('pending','running')");assert cr.fetchone()==(0,)
   cr.execute("SELECT count(*) FROM mp_event_delivery WHERE state='leased'");assert cr.fetchone()==(0,)
   set_control(cr,v['old_site'],v['old_release'],'paused');set_control(cr,v['new_site'],v['new_release'],'enabled')
   cr.execute('SELECT site_id,release_digest,state,generation FROM mp_dispatch_control ORDER BY site_id');after=cr.fetchall()
 print(json.dumps(dict(before=before,after=after,pending_or_running_jobs=0,leased_deliveries=0)))
finally:conn.close()
"""
args=['docker','run','--rm','-i','--name','mp-g7-production-dispatch-bootstrap','--label','com.modular.disposable='+s['project'],'--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',s['project']+'_runtime','--mount','type=volume,source='+s['project']+'_appconfig,target=/run/secrets,readonly','--entrypoint','/venv/bin/python',s['image_id'],'-c',code]
r=subprocess.run(args,input=json.dumps(request).encode(),capture_output=True,timeout=45);(LOCAL/'dispatch-bootstrap.stdout').write_bytes(r.stdout);(LOCAL/'dispatch-bootstrap.stderr').write_bytes(r.stderr);assert r.returncode==0,'Inspect actual clone DB before any repeat; do not reset/replay'
result=json.loads(r.stdout)
record=dict(result='owned_copy_old_scope_quarantined_new_site_dispatch_bootstrapped',utc=datetime.now(timezone.utc).isoformat(),application_image=s['image_id'],project=s['project'],database=s['active_db'],control=result,source_runtime_not_modified=True,external_worker_or_issuer_copied=False,limits=['Explicit NEW owned site bootstrap under local operator, not public HTTP authority, lifecycle approval or recovery evidence.','Copied source-site terminal history is preserved; old scope dispatch paused. New site emits events but no automatic worker/issuer authority is granted.'])
(OUT/'dispatch-bootstrap.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
