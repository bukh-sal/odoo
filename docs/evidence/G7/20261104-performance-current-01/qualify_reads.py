"""Bind the actual current read target and retire only exact obsolete helpers."""
import hashlib,json,math,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-performance-current-01'
def load(p):return json.loads(p.read_bytes())
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
record=load(ROOT/'.local/g7-performance-10k-01/state.json');state=load(PRIVATE/'alignment.json');read=load(OUT/'read-benchmark.json');resources=load(OUT/'resources.json');validation=load(OUT/'authenticated-dataset-validation.json')
assert state['phase']=='current_guarded_fixture_ready_needs_authenticated_validation' and load(PRIVATE/'read-progress.json')['phase']=='completed'
assert read['quality_target_passed'] and read['requests']==800 and read['total_errors']==0 and read['workspace_notes']==10000 and read['total_notes']==10006
assert read['dataset_sha256']==record['dataset']['dataset_sha256'] and read['image']==record['image_id']==state['target_image'] and read['generation']==30
assert read['benchmark17tables_and_fences_exact'] and read['original17tables_and_PG_worker_identity_exact'] and read['ordinary_auth_CSRF_binding_release_proxy_admission_retained']
assert validation['workspace_count']==10000 and validation['native_filtered_rows']==80 and validation['gateway_page_sizes']==[25,25] and validation['detail_bytes']==9600
assert set(read['cases'])=={'native_list80','native_detail','gateway_list25','gateway_detail'}
for case in read['cases'].values():
 assert case['concurrency']==case['independent_sessions']==20 and case['rounds']==10 and case['batch_pacing_seconds']==1.15 and not case['errors']
 samples=case['all_requests'];assert len(samples)==200 and all(s['status']==200 and s['ok'] and s['error'] is None and s['native_error'] is None for s in samples)
 assert round(sorted(s['latency_ms'] for s in samples)[math.ceil(.95*len(samples))-1],3)==case['timing']['p95_ms']<500
roles={r['role']:r for r in resources['runtimes']};selected=load(ROOT/'.local/releases/r1-0.1.23/images.json')['images']
for role,selected_role in [('benchmark_app','application'),('shared_database','postgres'),('benchmark_edge','proxy'),('preserved_original_worker','worker')]:assert roles[role]['image']==selected[selected_role]['image_id']
assert roles['shared_database']['nano_cpus']==1000000000 and roles['shared_database']['memory_limit_bytes']==536870912
assert resources['actual_app_settings']['workers']=='2' and resources['actual_app_settings']['max_cron_threads']=='0'
expected_proxy=(ROOT/'deploy/nginx-r0.conf').read_text();import re
expected_proxy=re.sub(r'\bapp:(8069|8072)\b',lambda m:record['app']+':'+m.group(1),expected_proxy)
assert call(['docker','exec',record['edge_id'],'cat','/etc/nginx/conf.d/default.conf']).decode()==expected_proxy
old=load(OUT.parent/'20261102-performance-10k-01/read-qualification.json');comparison={}
for name,case in read['cases'].items():comparison[name]=dict(prior31_p95_ms=old['metrics'][name]['p95_ms'],current14de_p95_ms=case['timing']['p95_ms'],prior_median_ms=old['metrics'][name]['median_ms'],current_median_ms=case['timing']['median_ms'])
retire=[]
old_record=load(PRIVATE/'record-before.json')
for ident in [old_record['app_id'],old_record['edge_id'],record['project']+'-core23-fixture-alignment']:
 data=json.loads(call(['docker','inspect',ident]))[0]
 assert data['Config']['Labels']['com.modular.disposable']==record['project'] and data['State']['Status']=='exited' and not data['State']['Running'] and data['State']['ExitCode']==0
 assert data['Id'] not in [record['app_id'],record['edge_id'],record['source_pg_container']]
 retire.append(dict(container_id=data['Id'],name=data['Name'],image=data['Image'],exit_code=0))
result=dict(result='passed_current_required_10k_20concurrent_standard_read_target',work_item='G-01c3',spec_section='24.1',utc=datetime.now(timezone.utc).isoformat(),image=record['image_id'],inventory=record['inventory_digest'],generation=30,shared_database_image=roles['shared_database']['image'],proxy_image=record['edge_image'],
 dataset=dict(workspace_notes=10000,total_notes=10006,synthetic_added=9976,detail_body_bytes=9600,sha256=read['dataset_sha256']),metrics={name:case['timing']|dict(errors=len(case['errors'])) for name,case in read['cases'].items()},requests=800,total_errors=0,
 unmodified_current_app_ordinary_authorized_paths=True,normal_CSRF_binding_release_and_proxy_admission=True,benchmark17tables_and_fences_exact=True,original17tables_PG_worker_identity_exact=True,selected_current_app_PG_proxy_images_exact=True,
 actual_environment=resources['docker'],app_limits=roles['benchmark_app'],shared_PG_limits=roles['shared_database'],comparison_to_prior31=comparison,warm_upstream_session_control=read['warm_sequential_upstream_session_control'],
 retired_exact_obsolete_helpers=retire,evidence_sha256={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['preflight.json','checkpoint.json','core-alignment.json','fixture-publication.json','current-ready.json','resources.json','authenticated-dataset-validation.json','read-benchmark.json']},
 limits=['Only1/2performance points: shell<3s,100mount/dispose cycles, R0/heartbeat/revocation mapping and fullG7 remain.',
 'ADR0054 unmanaged synthetic-fixture schema/publication initialization is not product lifecycle qualification; no issuer/executor/scheduler in clone.',
 'Gateway-list p95360.509ms versus prior254.463ms is retained; medians125.764vs127.169ms. Different image/dependencies/background environment; no controlled causal regression/improvement claim. All four current targets pass. Upstream session7.724ms versus coarse/different R0 context31ms is contextual.',
 f"Max~1.1s and all{sum(c['timing']['requests_over_500ms'] for c in read['cases'].values())}over500ms samples retained across800requests; p95 target is not a uniform latency bound. SharedPG/hardware/network/background containers and actual16CPU/~8GBengine are recorded; per-container limits unchanged.",
 'No image/volume/network/newdatabase or dataset reseed. Private checkpoint configuration/data remain protected, outside public/clean-log scope.'])
with (OUT/'read-qualification.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n');stream.flush()
for row in retire:
 actual=json.loads(call(['docker','inspect',row['container_id']]))[0];assert not actual['State']['Running'] and actual['State']['ExitCode']==0;assert call(['docker','rm',row['container_id']]).decode().strip()==row['container_id']
with (OUT/'helper-retirement.json').open('x',encoding='utf8') as stream:json.dump(dict(result='three_exact_successful_obsolete_fixture_containers_retired',containers=retire,images_volumes_networks_databases_removed=0),stream,indent=2);stream.write('\n')
state['phase']='current_read_target_qualified_remaining_performance';(PRIVATE/'alignment.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');record['state']='current_read_target_qualified_fixture_retained';(ROOT/'.local/g7-performance-10k-01/state.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=result['result'],p95_ms={name:m['p95_ms'] for name,m in result['metrics'].items()},requests=800,errors=0,retired_helpers=3)))
