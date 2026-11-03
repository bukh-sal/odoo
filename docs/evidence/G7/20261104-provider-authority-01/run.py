"""Current installed native and HTTP provider authority qualification."""
import hashlib,json,sys,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker,LOCAL
import r1_probe
f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==5
before=snapshot(state,'provider-authority-before');identity=worker(native,'provider-authority-worker-before');fixture=f.load(LOCAL/'fixtures.json')
source=(OUT/'native.py').read_text()
code='FIXTURE='+repr(fixture)+'\n'+source+"\nr=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProviderAuthority))\nenv.cr.rollback();print('MP_PROVIDER_AUTHORITY='+json.dumps(dict(tests=r.testsRun,successful=r.wasSuccessful(),failures=[t.id() for t,_ in r.failures],errors=[t.id() for t,_ in r.errors])))\nraise SystemExit(not r.wasSuccessful())\n"
name=state['project']+'-g7-provider-authority-01'
args=['docker','run','--rm','-i','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none','--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','1536m','--cpus','2','--pids-limit','128','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--entrypoint','/venv/bin/python',state['image_id'],'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0']
raw=f.command('provider-authority-native',args,input=code.encode(),timeout=180)
rows=[json.loads(line.split('MP_PROVIDER_AUTHORITY=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_PROVIDER_AUTHORITY=')];assert len(rows)==1 and rows[0]['successful']
assert snapshot(state,'provider-authority-after-native')==before
r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob')
notes={scope:actor.call('list',dict(limit=25),scope)['items'][0] for scope,actor in [('A',client),('B',bob)]}
spoof={'X-MP-Consumer':'administrator','X-MP-Actor':'root','X-MP-Plugin':'org.modularplatform.core'}
client.call('create',dict(title='Forbidden viewer attribution',body=''),workspace='B',headers=spoof,expect=403,code='FORBIDDEN')
client.call('get',dict(note_id=notes['B']['id']),headers=spoof,expect=404,code='NOT_FOUND')
client.call('create',dict(title='Strict authority fields',actor_id='administrator'),headers=spoof,expect=400,code='VALIDATION_FAILED')
document=f.load(ROOT/'docs/evidence/G7/20261104-core22-maintenance-01/state-after.json');wid=fixture['workspaces']['B']['public_id']
installation=next(i['installation_id'] for i in document['installations'] if i['plugin_id']=='org.example.notes_labels' and i['workspace_id']==wid)
binding=next(b for b in document['bindings'] if b['consumer_installation_id']==installation and b['workspace_id']==wid and b['alias']=='labels')
body=dict(api_version=binding['api_version'],request_id=__import__('uuid').uuid4().hex,input=dict(note_id=notes['B']['id'],expected_revision=notes['B']['revision'],labels=['Denied']))
status,value=client.request('/api/v1/services/'+binding['service_id']+'/set_labels',body,'B',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id'],**spoof});assert status==403 and value['error']['code']=='FORBIDDEN'
client.native('search_read',[[]],dict(context={'_mp_call_frame':{'principal_id':'administrator'}}),deny=True)
assert snapshot(state,'provider-authority-after-HTTP')==before and worker(native,'provider-authority-worker-after')==identity;f.guard(state)
gone=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=20);assert gone.returncode and b'no such' in gone.stderr.lower()
report=dict(result='passed_current_API07_provider_chain_and_attribution_authority',acceptance=['API-07'],image_id=state['image_id'],configuration_generation=5,native=rows[0],native_source_sha256=hashlib.sha256(source.encode()).hexdigest(),HTTP_checks=['viewer create denied despite forged consumer/actor/plugin headers','foreign note hidden despite forged attribution','actor fields rejected by strict schema','viewer labels provider call denied with forged headers','native RPC private frame rejected'],all_fixtures_rolled_back=True,all17tables_worker_original_configs_exact=True,helper_removed=True,limits=['Supported native call_bound and actual HTTP/legacy RPC attribution boundaries, not a sandbox against fully trusted native code.','No new plugin endpoint, actor impersonation mechanism, UI or grant schema introduced. No ID08 browser, API03 cancellation or API05 crash qualification claim.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],native_tests=rows[0]['tests'],HTTP_checks=5,all17tables_worker_exact=True)))
