"""Bounded secondary current-image request faults; main application unchanged."""
import argparse,hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-request-faults-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker,LOCAL
from modular_platform.operator_os import protect_directory
import r1_probe,rfc8785
f.OUTPUT=OUT
def load(path):return json.loads(path.read_bytes())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
def command(label,args):return f.command('request-fault-'+label,args,timeout=60)
def marker(value):write(PRIVATE/'state.json',value)
def save(name,value):
 with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def setup():
 state,native=context('connector');assert native.config['generation']==5 and not PRIVATE.exists()
 with socket.socket() as check:check.bind(('127.0.0.1',18091))
 protect_directory(PRIVATE);arm=protect_directory(PRIVATE/'arm');proxy=protect_directory(PRIVATE/'proxy')
 record=dict(state='preparing',image_id=state['image_id'],secondary=state['project']+'-g7-request-fault01',edge=state['project']+'-g7-request-fault-edge01',port=18091,owned=[])
 marker(record)
 write(PRIVATE/'data-before.json',snapshot(state,'request-fault-data-before'));write(PRIVATE/'worker-before.json',worker(native,'request-fault-worker-before'))
 for name in [record['secondary'],record['edge']]:assert subprocess.run(['docker','inspect',name],capture_output=True).returncode
 write(arm/'arm.json',dict(nonce=uuid4().hex,database='NOT_ARMED',principal_id='',workspace_id='',service='',method='',key='NOT_ARMED',input_sha256=''))
 (proxy/'default.conf').write_text('server {listen 8069; server_name _; access_log off; error_log /dev/stderr crit; location ^~ /web/database {return 403;} location / {proxy_set_header Host $http_host; proxy_pass http://'+record['secondary']+':8069;}}\n')
 args=['docker','create','--name',record['secondary'],'--label','com.modular.disposable='+state['project'],'--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_runtime','--memory','1g','--cpus','2','--pids-limit','256','--tmpfs','/tmp:rw,nosuid,nodev,size=128m,mode=1777','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--mount','type=bind,source='+str(arm)+',target=/run/mp-fault,readonly','--env','MP_R1_FAULT_FILE=/run/mp-fault/arm.json','--entrypoint','/venv/bin/python',state['image_id'],'odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db'],'--addons-path=/opt/modular/addons,/opt/modular/fixtures/v1','--load=base,web,mp_r1_fault','--workers=2','--max-cron-threads=0','--log-level=error']
 command('create-secondary',args)
 out=(PRIVATE/'secondary.stdout').open('xb');err=(PRIVATE/'secondary.stderr').open('xb');attached=subprocess.Popen(['docker','start','-a',record['secondary']],stdout=out,stderr=err);out.close();err.close()
 record.update(state='secondary_starting',attach_pid=attached.pid);marker(record)
 proxyimage=load(ROOT/'deploy/runtime.lock.json')['reverse_proxy_image']
 command('create-edge',['docker','create','--name',record['edge'],'--label','com.modular.disposable='+state['project'],'--log-driver','none','--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_edge','--publish','127.0.0.1:18091:8069','--tmpfs','/var/cache/nginx:rw,uid=101,gid=101,mode=0755','--tmpfs','/var/run:rw,uid=101,gid=101,mode=0755','--mount','type=bind,source='+str(proxy)+',target=/etc/nginx/conf.d,readonly','--entrypoint','nginx',proxyimage,'-g','daemon off;'])
 command('connect-edge',['docker','network','connect',state['project']+'_runtime',record['edge']]);command('start-edge',['docker','start',record['edge']])
 fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;deadline=time.monotonic()+45
 while True:
  try:r1_probe.Client({**state,'port':18091},fixture);break
  except (OSError,AssertionError):
   assert inspect(record['secondary'])['State']['Running'] and attached.poll() is None
   if time.monotonic()>deadline:raise
   time.sleep(.25)
 record['state']='ready';marker(record);f.guard(state)
 print(json.dumps(dict(result='secondary_exact_image_fault_profile_ready',port=18091,main_unchanged=True)),flush=True)
def logs():return (PRIVATE/'secondary.stdout').read_bytes()+(PRIVATE/'secondary.stderr').read_bytes()
def wait_marker(record,text,nonce,timeout=20):
 deadline=time.monotonic()+timeout
 while True:
  matches=[line.decode(errors='replace') for line in logs().splitlines() if text.encode() in line and nonce.encode() in line]
  if matches:return matches
  assert inspect(record['secondary'])['State']['Running']
  if time.monotonic()>deadline:raise RuntimeError('Exact postcommit marker not observed; reconcile recorded key, do not resend')
  time.sleep(.1)
def arm(record,fixture,item,mode):
 nonce=uuid4().hex;item.update(nonce=nonce,mode=mode)
 record['owned'].append(item);record['state']=mode+'_prepared';marker(record)
 write(PRIVATE/'arm/arm.json',dict(fault=mode,nonce=nonce,database=fixture['database'],principal_id=fixture['users']['alice']['principal_id'],workspace_id=fixture['workspaces']['A']['public_id'],service='org.example.notes.documents',method='create',key=item['key'],input_sha256=hashlib.sha256(rfc8785.dumps(item['values'])).hexdigest()))
def checks():
 state,native=context('connector');record=load(PRIVATE/'state.json');assert record['state']=='ready' and native.config['generation']==5
 fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;primary=r1_probe.Client(state,fixture);secondary=r1_probe.Client({**state,'port':record['port']},fixture)
 nonce=uuid4().hex;item=dict(key='parallel-'+nonce,values=dict(title='Owned parallel '+nonce,body='Same database effect'))
 record['owned'].append(item);record['state']='parallel_inflight';marker(record)
 clients=[r1_probe.Client(state,fixture) for _ in range(8)]
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda client:client.call('create',item['values'],key=item['key']),clients))
 assert all(result==results[0] for result in results);item['note']=results[0];record['state']='parallel_verified';marker(record)
 assert primary.native('search_count',[[('title','=',item['values']['title'])]])==1
 crash=dict(key='crash-'+nonce,values=dict(title='Owned postcommit crash '+nonce,body='Committed before lost response'));arm(record,fixture,crash,'exit_after_commit')
 record['state']='crash_inflight';marker(record)
 code,value=secondary.request('/api/v1/services/org.example.notes.documents/create',dict(api_version='1.0',request_id=uuid4().hex,idempotency_key=crash['key'],input=crash['values']),'A',{'X-CSRFToken':secondary.csrf,'X-MP-Binding':fixture['bindings']['A']['binding_id']})
 assert code==502,code;events=wait_marker(record,'MP_R1_POSTCOMMIT_EXIT',crash['nonce']);assert len(events)==1
 assert primary.native('search_count',[[('title','=',crash['values']['title'])]])==1
 crash['note']=primary.call('create',crash['values'],key=crash['key']);assert primary.call('create',crash['values'],key=crash['key'])==crash['note'];crash['events']=events;crash['lost_response_status']=code;record['state']='crash_verified';marker(record)
 delay=dict(key='cancel-'+nonce,values=dict(title='Owned postcommit cancellation '+nonce,body='Committed before abort'));arm(record,fixture,delay,'delay_after_commit')
 release=secondary.request('/api/v1/client-release')[1]['data'];trigger=PRIVATE/'cancel.trigger';assert not trigger.exists()
 cfg=dict(base=secondary.base,csrf=secondary.csrf,cookie='; '.join(c.name+'='+c.value for c in secondary.jar),workspace=fixture['workspaces']['A']['public_id'],release=release,binding=fixture['bindings']['A'],values=delay['values'],key=delay['key'],trigger=str(trigger))
 record['state']='cancel_inflight';marker(record)
 with (PRIVATE/'cancel.stdout').open('xb') as out,(PRIVATE/'cancel.stderr').open('xb') as err:
  child=subprocess.Popen(['node',str(OUT/'cancel.mjs')],stdin=subprocess.PIPE,stdout=out,stderr=err);record['cancel_pid']=child.pid;marker(record);child.stdin.write(json.dumps(cfg).encode());child.stdin.close()
  starts=wait_marker(record,'MP_R1_POSTCOMMIT_DELAY_START',delay['nonce']);assert len(starts)==1
  assert primary.native('search_count',[[('title','=',delay['values']['title'])]])==1
  trigger.write_text('cancel after observed commit\n');assert child.wait(timeout=30)==0,'Inspect exact Node result; never blindly rerun mutation'
 results=[json.loads(line) for line in (PRIVATE/'cancel.stdout').read_text().splitlines()];assert len(results)==2 and results[0]['outcome']=='not_started' and results[1]['outcome']=='unknown'
 ends=wait_marker(record,'MP_R1_POSTCOMMIT_DELAY_END',delay['nonce']);assert len(ends)==1
 delay['note']=primary.call('create',delay['values'],key=delay['key']);assert primary.call('create',delay['values'],key=delay['key'])==delay['note'];delay.update(events=starts+ends,SDK_results=results);record['state']='cancel_verified';marker(record)
 deadline_title='Never created deadline '+nonce
 error=primary.call('create',dict(title=deadline_title,body=''),key='deadline-'+nonce,expect=504,code='DEADLINE_EXCEEDED',headers={'X-MP-Deadline-Ms':'0'})
 assert error['error']['details']['outcome']=='not_started' and primary.native('search_count',[[('title','=',deadline_title)]])==0
 record['state']='checks_verified_cleanup_pending';marker(record)
 save('request-results.json',dict(result='passed_current_concurrency_crash_and_SDK_cancel',concurrent_requests=8,parallel_identical_one_effect=True,crash=crash,cancel=delay,deadline=dict(status=504,outcome='not_started',record_created=False),image_id=state['image_id'],SDK_source_sha256=hashlib.sha256((ROOT/'platform_addons/mp_shell/static/src/host.js').read_bytes()).hexdigest(),fault_source_sha256=hashlib.sha256((ROOT/'tests/fixtures/addons/v1/mp_r1_fault/controllers.py').read_bytes()).hexdigest()))
 print(json.dumps(dict(result='checks_passed_cleanup_pending',concurrency=8,postcommit_exit=86,SDK_cancel='unknown',deadline='not_started')),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','checks']);args=parser.parse_args();globals()[args.action]()
