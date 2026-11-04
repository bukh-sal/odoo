"""Republish current guarded metadata for the unmanaged read fixture only."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();PRIVATE=ROOT/'.local/g7-performance-current-01';OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import OBSERVE_SQL
from modular_platform.plans import data_digest,release_lock
from modular_platform.projection import runtime_inputs,project_deployment,public_profile
from modular_platform.resolution import resolve_release
from modular_platform.profile_channel import PROFILE_WRITER
def load(p):return json.loads(p.read_bytes())
record=load(PRIVATE/'record-before.json');state=load(PRIVATE/'alignment.json');assert state['phase']=='current_core_initialized_tables_exact_needs_publication'
assert record['database']=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c' and record['project']=='mp-g7-perf-6fafdba2c44c'
def command(label,args,*,data=None,timeout=120):
 with (PRIVATE/'logs'/(label+'.stdout')).open('xb') as out,(PRIVATE/'logs'/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=data,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect phase/profile/DB before continuation; never replay initialization'
 return (PRIVATE/'logs'/(label+'.stdout')).read_bytes()
def sql(label,query):return command(label,['docker','exec','-i',record['source_pg_container'],'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database']],data=query.encode())
site=json.loads(sql('observe-aligned-benchmark-site',OBSERVE_SQL));runtime=load(PRIVATE/'new-runtime.json');prior=load(PRIVATE/'benchmark-publication-before.json');old=prior['profile']['configuration'];old_lock=old['published_release']
assert site['site_id']==prior['params']['mp.site_id'] and all(i['metadata_state']=='installed' for i in site['installations'])
catalog=Catalog(ROOT/'.local/release-kit-rehearsal/private/catalog',configuration(ROOT/'.local/releases/r1-0.1.23/plugins/curated-trust.json'),readonly=True);snapshot=catalog.snapshot()
external=[p for p in old_lock['plugins'] if p['runtime']=='external_service']
assert external and all(f['feature_state']=='suspended' for f in site['features'] if f['plugin_id'] in {p['plugin_id'] for p in external})
selected,environment,provenance=runtime_inputs(runtime,snapshot,external_plugins=external)
ids={i['installation_id']:i['plugin_id'] for i in site['installations']};choices={}
for row in site['bindings']:
 binding=row['descriptor'];choices[(ids[binding['consumer_installation_id']],binding['alias'],binding['site_id'],binding['workspace_id'])]=binding['provider_plugin_id']
resolved=resolve_release(selected,runtime['python_metadata'],environment,{r['manifest']['plugin']['id']:'=='+r['manifest']['plugin']['version'] for r in selected},core_python=[r['name']+'=='+r['version'] for r in runtime['python_metadata']],scoped_provider_choices=choices)
created=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ');generation=int(prior['params']['mp.release_generation'])+1;lock=release_lock(resolved,provenance,generation=generation,created_at=created)
config=dict(schema_version=1,deployment_id=prior['params']['mp.deployment_id'],project=record['project'],image_id=state['target_image'],generation=generation,policy_version=old['policy_version'],operator_authorization_generation=old['operator_authorization_generation'],release_created_at=created,sites=[dict(site_id=site['site_id'],database=record['database'])],published_release=lock)
# This explicit OS fixture policy denies all external endpoints; no copied
# cache value is promoted into worker/issuer authority.
observation=dict(image_id=state['target_image'],runtime=runtime,sites=[site],external_state=dict(endpoints=[],service_health={}))
pins={'mp.release_generation':str(generation),'mp.release_digest':data_digest(lock),'mp.active_inventory_digest':state['target_inventory'],'web.base.url':'http://g7perf.localhost:'+str(record['port']),'web.base.url.freeze':'True'}
for name,value in [('fixture-configuration.json',config),('fixture-publication-pins.json',pins)]:
 with (PRIVATE/name).open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
state['phase']='publishing_current_fixture_release_metadata';(PRIVATE/'alignment.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
payload=json.dumps(pins).replace("'","''")
sql('set-only-benchmark-release-pins',"INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date) SELECT key,value,1,1,timezone('UTC',now()),timezone('UTC',now()) FROM jsonb_each_text('"+payload+"'::jsonb) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value;")
observation['sites']=[json.loads(sql('observe-pinned-benchmark-site',OBSERVE_SQL))]
document=project_deployment(config,observation,snapshot);profile=public_profile(config,observation,snapshot,created)
with (PRIVATE/'current-fixture-profile.json').open('x',encoding='utf8') as stream:json.dump(profile,stream,indent=2);stream.write('\n')
result=json.loads(command('publish-benchmark-public-profile',['docker','run','--rm','-i','--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--network',record['source_runtime_network'],
 '--mount','type=volume,source='+record['volume']+',target=/run/secrets,volume-subpath=config,readonly','--entrypoint','/venv/bin/python',state['target_image'],'-c',PROFILE_WRITER],data=json.dumps(profile).encode()))
assert result['profile_published'] is True and result['site_id']==site['site_id'] and document['state']['release_digest']==pins['mp.release_digest']
state.update(phase='current_fixture_published_needs_guarded_app',generation=generation,release_digest=pins['mp.release_digest']);(PRIVATE/'alignment.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
report=dict(result='current_unmanaged_fixture_public_metadata_published',image=state['target_image'],inventory=state['target_inventory'],generation=generation,release_digest=pins['mp.release_digest'],external_endpoints=[],external_features_suspended=True,issuer_or_executor_registered=False,projection_and_profile_writer_unchanged=True,limits=['OS-side synthetic benchmark metadata initialization under ADR0054; public profile grants no approval or technical authority.','Guarded app start and actual current read measurements remain unqualified.'])
with (OUT/'fixture-publication.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],generation=generation,release_digest=state['release_digest'])))
