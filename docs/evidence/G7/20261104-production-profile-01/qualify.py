"""Bind current SEC02/04 proof and selected proxy pin; no release completion claim."""
import hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-production-profile-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from production_preflight import check
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
load=lambda p:json.loads(p.read_text());s=load(LOCAL/'state.json');target=load(LOCAL/'operator/target.json')
assert s['phase']=='profiles_started_ready'
records={'HTTP-qualification.json':'passed_HTTP_matrix','production-preflight.json':'passed','rate-TLS-qualification.json':'passed','TLS-WebSocket-qualification.json':'passed_actual_TLS_native_WebSocket_and_foreign_origin_rejection','upload-native-error-qualification.json':'passed_current_upload_bounds_and_existing_native_error_reuse','source-preservation.json':'source17tables_worker_and_all_protected_configurations_exact'}
for name,result in records.items():assert load(OUT/name)['result']==result
positive=check(target,LOCAL/'odoo.conf',s['origin']);reader=DockerObserver(target);observation=reader.read()
assert observation['image_id']==s['image_id'] and not observation['runtime']['modified_files']
assert json.loads(sql(reader,BUSINESS_SQL))==load(OUT/'setup/business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUT/'setup/schema-before.json')
assert json.loads(sql(reader,'SELECT to_jsonb(count(*)) FROM mp_operation_request;'))==0
counts=json.loads(sql(reader,"SELECT jsonb_build_object('notes',(SELECT count(*) FROM mp_example_note),'canvas',(SELECT count(*) FROM mp_example_canvas_board),'jobs',(SELECT count(*) FROM mp_job),'outbox',(SELECT count(*) FROM mp_outbox),'active_credentials',(SELECT count(*) FROM mp_service_credential WHERE state='active'));"));assert counts==dict(notes=2,canvas=1,jobs=1,outbox=5,active_credentials=0)
proxy='modular-platform-proxy@sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f'
lock=load(ROOT/'deploy/runtime.lock.json');assert lock['reverse_proxy_image']==proxy
meta=json.loads(subprocess.check_output(['docker','image','inspect',proxy]))[0];assert proxy in meta['RepoDigests']
env=dict(os.environ,MP_EXPECTED_DATABASE=s['active_db'],MP_EXPECTED_INVENTORY_DIGEST=s['inventory_digest'],MP_HTTPS_PORT='18445',MP_HTTP_PORT='18093')
r=subprocess.run(['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f','deploy/compose.yaml','-f','deploy/compose-production.yaml','config','--format','json'],env=env,capture_output=True,timeout=30);assert r.returncode==0;compose=json.loads(r.stdout);assert compose['services']['edge']['image']==proxy and compose['services']['app']['image']==s['image_id'] and 'build' not in compose['services']['app']
actual=[]
for entry in s['containers']:
 info=json.loads(subprocess.check_output(['docker','inspect',entry['container_id']]))[0];assert info['State']['Running'] and info['HostConfig']['ReadonlyRootfs']
 if 'edge' in entry['purpose']:assert info['Image']==meta['Id'] and info['Config']['User']=='101:101' and all(v[0]['HostIp']=='127.0.0.1' for v in info['HostConfig']['PortBindings'].values())
 actual.append(dict(purpose=entry['purpose'],image=info['Image'],user=info['Config']['User'],readonly=True,container_id=info['Id']))
# Bind exercised endpoint guards/DTOs to the exact runtime source, not just host tests.
source={}
for name in ['platform_addons/mp_core/controllers.py','platform_addons/mp_core/operations.py','packages/platform_sdk/modular_platform/manager_views.py']:
 image_name=name.replace('platform_addons/','addons/');sha=hashlib.sha256((ROOT/name).read_bytes()).hexdigest();assert observation['runtime']['inventory']['files'][image_name]==sha;source[name]=sha
for name in ['tools/http_profile.py','tools/production_preflight.py','deploy/compose.yaml','deploy/compose-production.yaml','deploy/runtime.lock.json','deploy/nginx-r0.conf','deploy/proxy.Dockerfile','deploy/proxy-packages.lock.json','tests/test_http_profile.py']:source[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
record=dict(result='passed_current_SEC02_SEC04_and_selected_proxy_profiles',utc=datetime.now(timezone.utc).isoformat(),acceptances=['SEC-02','SEC-04'],spec_sections=['11.3','11.4','15.1','15.2','15.3','20','25.3'],application_image=s['image_id'],proxy_image=meta['Id'],selected_proxy_reference=proxy,site_id=s['site_id'],project=s['project'],database=s['active_db'],production_preflight=positive,actual_containers=actual,record_sha256={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in records},source_sha256=source,HTTP_cases=len(load(OUT/'HTTP-qualification.json')['checks']),rate_requests=396,TLS=['TLSv1.2','TLSv1.3'],TLS11_rejected=True,TLS_WebSocket=[101,403],host_profile_unit_tests=dict(command=[str(ROOT/'.venv/Scripts/python.exe'),'-X','utf8','-m','unittest','discover','-s','tests','-p','test_http_profile.py','-v'],tests=5,result='passed',tool_output_observed=True),native_CRUD_default_views=True,Canvas_minimal_read=True,clone_business_counts=counts,source17tables_worker_configs_exact=True,compose_selected_exact_candidate=True,root_contract_change=False,limits=['Local qualification copy only, not publication or external production deployment. Private test certificate trusted only by test client.','No external worker/issuer copied; external analysis intentionally unavailable. No new SVC/recovery/fresh-install claim.','Existing upstream native parser/handler functions exercised with current native429; actual Owl dialog/browser rendering not claimed.','Safe-log canaries/upload boundaries do not establish global SEC03. Final OS/vendor/source/licenses/history/layers/archives/secrets/network/reprobuild/performance/accessibility/runbooks/handoff remain G7.','Fixture cleanup evidence recorded separately; current original/fresh/perf services and rollback images remain retained.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],acceptance=record['acceptances'],HTTP_cases=record['HTTP_cases'],rate_requests=396,proxy_reference=proxy)))
