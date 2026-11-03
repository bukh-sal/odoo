"""Explicit input/namespace/startup regressions on the deployed candidate."""
import importlib.util,json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('core21_extra_activation',OUT/'activate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
spec=importlib.util.spec_from_file_location('core21_extra_clients',ROOT/'docs/evidence/G6/20261102-worker-image-success-01/remote.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
f=m.f;f.OUTPUT=OUT;state,native=m.context();before=m.snapshot(state,'core21-extra-guards-before');client=old.s.client(state,'alice')
saved=f.load(m.j.LOCAL/'notes-stats-remote-01/positive.json');job=f.load(m.PRIVATE/'remote-job.json');assert job['state']=='verified'
body=dict(api_version='1.0',request_id='core21-conflict',idempotency_key=job['key'],input=dict(note_id=saved['note_id'],expected_revision=saved['revision']+1))
status,value=client.request('/api/v1/services/org.example.notes_stats.jobs/analyze',body,workspace='C',headers={'X-CSRFToken':client.csrf,'X-MP-Binding':saved['jobs_binding']})
assert status==409 and value['error']['code']=='CONFLICT'
status,value=client.request('/jsonrpc',dict(jsonrpc='2.0',method='call',id=1,params=dict(service='common',method='version',args=[])));assert status==404
name=state['project']+'-core21-data-addon-refusal'
code="import os,pathlib,sys;p=pathlib.Path('/var/lib/modular/addons');p.mkdir();(p/'unexpected.py').write_text('raise RuntimeError(\"untrusted import must not execute\")');os.execv(sys.executable,[sys.executable,'/opt/modular/tools/start_worker.py','-c','/run/secrets/odoo_config'])"
args=['docker','run','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none','--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--tmpfs','/tmp','--tmpfs','/var/lib/modular:rw,uid=10001,gid=10001,mode=0700','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--env','MP_EXPECTED_DATABASE='+state['active_db'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],'--entrypoint','/venv/bin/python',state['image_id'],'-B','-c',code]
prefix=m.j.LOCAL/'logs/core21-data-addon-refusal'
with prefix.with_suffix('.stdout').open('xb') as out,prefix.with_suffix('.stderr').open('xb') as err:r=subprocess.run(args,stdout=out,stderr=err,timeout=60)
assert r.returncode==1 and 'Unexpected writable data-dir addon search-path content' in prefix.with_suffix('.stderr').read_text()
assert m.snapshot(state,'core21-extra-guards-after')==before
f.save('extra-guards.json',dict(result='passed_current_idempotency_conflict_legacy_rpc_omission_data_addon_refusal',configuration_generation=30,image_id=state['image_id'],same_key_replay_positive='remote-job.json',changed_input_conflicts409=True,legacy_jsonrpc_omitted404=True,actual_current_image_data_addon_injection_refused_before_native_import=True,
 injected_container=name,injected_exit=1,captured37jobs_other16tables_exact=True,
 limits=['Actual supported-entrypoint and wire checks, not hostile-native containment or a full final release/security audit.']))
print('Actual current idempotency conflict409, legacy JSONRPC omission404 and writable-addon startup refusal pass; data exact')
