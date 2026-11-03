"""Current gateway negatives and actual stale-image startup refusal."""
import importlib.util,json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('core21_final_gateway',OUT/'activate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
spec=importlib.util.spec_from_file_location('core21_client_factory',ROOT/'docs/evidence/G6/20261102-worker-image-success-01/remote.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==30
before=m.snapshot(state,'core21-gateway-negative-before');worker=m.worker(native,'core21-gateway-negative-worker-before')
client=old.s.client(state,'alice')
client.call('sudo',{},expect=404,code='NOT_FOUND')
denial=client.call('create',dict(title='Denied metadata injection',body='',actor_id='administrator'),expect=400,code='VALIDATION_FAILED')
assert 'debug' not in json.dumps(denial) and 'traceback' not in json.dumps(denial)
status,value=client.request('/api/v1/operations/installed');assert status==403 and value['error']['code']=='FORBIDDEN'
client.native('search_read',[[]],dict(fields=['id']),model='mp.plugin.installation',deny=True)
client.native('create',[dict(plugin_id='org.example.denied')],model='mp.plugin.installation',deny=True)
before_runtime=f.load(ROOT/'.local/g7-core21-dependencies-image-01/before-runtime.json')
name=state['project']+'-core21-stale-image-refusal'
args=['docker','run','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none','--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--env','MP_EXPECTED_DATABASE='+state['active_db'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+before_runtime['inventory_digest'],'sha256:31a673ebbc53fbdecbc5cbfdb5f0eac30d11367630da306d47b5e14cfce17345']
prefix=m.j.LOCAL/'logs/core21-stale-image-refusal'
with prefix.with_suffix('.stdout').open('xb') as out,prefix.with_suffix('.stderr').open('xb') as err:result=subprocess.run(args,stdout=out,stderr=err,timeout=60)
assert result.returncode==124,'Inspect exact stale helper; never retry startup'
diagnostic=prefix.with_suffix('.stderr').read_text();assert 'version' in diagnostic.lower() and ('native' in diagnostic.lower() or 'platform' in diagnostic.lower())
assert m.snapshot(state,'core21-gateway-negative-after')==before and m.worker(native,'core21-gateway-negative-worker-after')==worker
f.save('gateway-startup-guards.json',dict(result='passed_current_gateway_operator_boundaries_and_stale_startup_refusal',configuration_generation=30,image_id=state['image_id'],
 checks=['undeclared sudo method404 NOT_FOUND','schema actor injection400 VALIDATION_FAILED without debug/traceback','workspace administrator denied manager API403','workspace administrator denied native installation read/create','actual previous31 image exits124 on current core21 native version before serving'],
 stale_container=name,stale_exit=124,all37jobs_other16tables_worker_exact=True,
 limits=['Supported startup/HTTP boundaries only; trusted native code can bypass an entrypoint, no sandbox claim.','Full production TLS/proxy/network/secrets/provenance/failure-recovery qualification remains.']))
print('Current schema/declared-method/operator/native metadata boundaries and actual stale startup refusal pass; all captured data/worker exact')
