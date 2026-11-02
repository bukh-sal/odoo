"""Reconcile successful init; distinguish catalog-only uninstallable rows."""
import json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core21-fresh-registry-01'
record=json.loads((PRIVATE/'state.json').read_text());assert record['state']=='initializing_fresh_core_registry'
def call(label,args,raw=None):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=raw,stdout=out,stderr=err,timeout=90)
 assert r.returncode==0,'Inspect '+label+'; no replay'
 return (PRIVATE/(label+'.stdout')).read_bytes()
info=json.loads(call('init-terminal-inspection',['docker','inspect','--type','container',record['init_container']]))[0]
assert info['Image']==record['image_id'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
assert info['Config']['Labels']['com.modular.disposable']==record['project']
assert all(m['Type']=='volume' and m['Name']==record['volume'] for m in info['Mounts'])
modules=json.loads((PRIVATE/'fresh-modules.stdout').read_text());installed=[m for m in modules if m['state']=='installed']
unavailable=[m for m in modules if m['state']=='uninstallable']
allowed=set(json.loads((ROOT/'.local/g7-core21-dependencies-image-01/candidate-runtime.json').read_text())['inventory']['native_addons'])
assert installed and all(m['name'] in allowed for m in installed)
assert len(installed)+len(unavailable)==len(modules) and all(m['version'] is None for m in unavailable)
assert next(m for m in installed if m['name']=='mp_core')['version']=='19.0.0.1.21'
tables=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT encode(sha256(convert_to(jsonb_build_object("+','.join("'"+name+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+name+" t),'[]'::jsonb)" for name in tables)+")::text,'UTF8')),'hex'); ROLLBACK;"
after=call('source-preservation-final',['docker','exec','-i',record['shared_pg'],'psql','-X','-qAt','-U','postgres','-d',record['source_database'],'-v','ON_ERROR_STOP=1'],query.encode()).strip().decode()
assert after==(PRIVATE/'source-before.stdout').read_text().strip()
old=json.loads((PRIVATE/'worker-before.stdout').read_text())[0]
worker=json.loads(call('worker-preservation-final',['docker','inspect','--type','container',old['Id']]))[0]
assert worker['State']['Running'] and all(worker[key]==old[key] for key in ['Id','Image','RestartCount']) and worker['State']['StartedAt']==old['State']['StartedAt']
call('retire-terminal-init',['docker','rm',info['Id']])
absent=subprocess.run(['docker','inspect','--type','container',info['Id']],capture_output=True,timeout=30);assert absent.returncode!=0 and b'no such' in absent.stderr.lower()
record['state']='fresh_core_registry_passed_retained_for_http_and_release_rehearsal';record['terminal_init_retired']=info['Id']
(PRIVATE/'state.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
report=dict(result='passed_empty_database_native_core_initialization',**record,installed_modules=installed,uninstallable_catalog_only=unavailable,
 source_17table_sha256=after,source_17tables_worker_exact=True,
 attempts=['Seed chown-before-chmod denied; exact existing config permissions corrected without regenerating bytes/database.',
 'Continuation reporting alias NameError before fix/init; bound recorded aliases, no mutation repeated.',
 'Native init completed0, registry loaded; result assertion incorrectly included uninstallable catalog placeholders. Finalizer verifies installed-only graph and retains all metadata observations; no init rerun.'],
 limits=['No HTTP/login/plugin-install/current acceptance pass yet; bootstrap-only registry probe, not approved live deployment.',
 'One new owned database/config-data volume retained for required HTTP/fresh-release follow-up; terminal init retired.',
 'Shared PostgreSQL/network/trusted DB role explicitly retained; not hostile-native isolation.'])
with (OUT/'fresh-registry.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],installed=len(installed),uninstallable_catalog_only=len(unavailable),original_preserved=True,terminal_init_retired=True)))
