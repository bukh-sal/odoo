"""Bind actual reference read measurements; do not pass all performance/G7."""
import hashlib,importlib.util,json,re
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('perf10k_qualification_fixture',OUT/'fixture.py');q=importlib.util.module_from_spec(sp);sp.loader.exec_module(q)
m,f=q.m,q.f;f.OUTPUT=OUT;source,native=m.context();record=f.load(q.PRIVATE/'state.json')
assert native.config['generation']==29 and record['image_id']==source['image_id'] and record['state']=='prepared_needs_HTTP_dataset_validation'
read=f.load(OUT/'read-benchmark.json');validation=f.load(OUT/'authenticated-dataset-validation.json');resources=f.load(OUT/'resources.json')
assert read['quality_target_passed'] and read['target10000_dataset_met'] and read['workspace_notes']==10000 and read['total_notes']==10006 and read['all17tables_worker_exact']
assert validation['workspace_count']==10000 and validation['gateway_pages_disjoint'] and validation['detail_body_bytes']==9600
names={'native_list80','native_detail','gateway_list25','gateway_detail'};assert set(read['cases'])==names
metrics={}
for name,case in read['cases'].items():
 assert case['concurrency']==20 and case['independent_sessions']==20 and case['rounds']==10 and not case['errors']
 samples=case['all_requests'];assert len(samples)==200 and all(v['ok'] and v['status']==200 for v in samples)
 assert case['timing']['p95_ms']<500
 metrics[name]=case['timing']|dict(requests_over_500ms=sum(v['latency_ms']>=500 for v in samples),errors=0)
assert resources['actual_workspace_notes']==10000 and resources['concurrent_requests']==20
roles={r['role']:r for r in resources['runtimes']}
assert roles['benchmark_app']['nano_cpus']==2000000000 and roles['benchmark_app']['memory_limit_bytes']==1610612736
assert roles['shared_database']['nano_cpus']==1000000000 and roles['shared_database']['memory_limit_bytes']==536870912
assert resources['actual_app_settings']['workers']=='2' and resources['actual_app_settings']['max_cron_threads']=='0'
original=f.load(q.PRIVATE/'source-data-before.json');original_worker=f.load(q.PRIVATE/'source-worker-before.json')
assert m.snapshot(source,'perf10k-qualify-source-after')==original and m.worker(native,'perf10k-qualify-worker-after')==original_worker
status=json.loads(f.sql(source,'perf10k-qualify-copied-fences',"BEGIN READ ONLY; SELECT jsonb_build_object('dispatch',(SELECT jsonb_agg(state) FROM mp_dispatch_control),'credentials_active',(SELECT count(*) FROM mp_service_credential WHERE state='active'),'jobs',(SELECT count(*) FROM mp_job),'outbox',(SELECT count(*) FROM mp_outbox),'dataset_sha256',(SELECT encode(sha256(convert_to(jsonb_agg(to_jsonb(n) ORDER BY id)::text,'UTF8')),'hex') FROM mp_example_note n)); ROLLBACK;",database=record['database']))
assert status==dict(dispatch=['paused'],credentials_active=0,jobs=36,outbox=49,dataset_sha256=record['dataset']['dataset_sha256'])
source_proxy=f.command('perf10k-qualify-source-proxy',['docker','exec',source['project']+'-edge-1','cat','/etc/nginx/conf.d/default.conf']).decode()
benchmark_proxy=f.command('perf10k-qualify-benchmark-proxy',['docker','exec',record['edge_id'],'cat','/etc/nginx/conf.d/default.conf']).decode()
expected=re.sub(r'\bapp:(8069|8072)\b',lambda v:record['app']+':'+v.group(1),source_proxy)
assert expected==benchmark_proxy
paths=['fixture.py','read_benchmark.py','fixture.json','read-benchmark.json','authenticated-dataset-validation.json','resources.json','host-hardware.json']
f.save('read-qualification.json',dict(result='passed_required_10k_20concurrent_standard_read_target',work_item='G-01c3',spec_section='24.1',source_configuration_generation=29,source_dispatch_generation=132,image=source['image_id'],inventory=source['inventory_digest'],dataset=dict(total_notes=10006,workspace_notes=10000,synthetic_added=9976,detail_body_bytes=9600,sha256=status['dataset_sha256']),metrics=metrics,measured_requests=800,total_errors=0,
 normal_authenticated_actor_workspace_native_and_gateway_paths=True,release_CSRF_binding_authorization_and_proxy_admission_retained=True,proxy_security_admission_config_only_upstream_hostname_changed=True,
 source17tables_36jobs_30Notes_worker_unchanged=True,benchmark_dataset_exact_after_reads=True,copied_dispatch_paused_credentials_revoked_no_new_jobs_or_events=True,
 app_CPUs=2,app_memory_bytes=1610612736,workers=2,shared_PG_CPUs=1,shared_PG_memory_bytes=536870912,
 source_sha256={p:hashlib.sha256((OUT/p).read_bytes()).hexdigest() for p in paths},one_owned_reusable_fixture_no_new_image=True,
 limits=['Read portion only: shell<3s,100custom-page mount/dispose cycles, relevant R0 comparison, heartbeat/revocation mapping and fullG7 remain.','Logical separateDB/app/proxy/filestore; PostgreSQL process and physical hardware/network shared with original idle/available runtime, not dedicated hardware.','Engine/resource/clock/storage metadata and host CPU/disk models recorded; Docker VHD-to-physical-disk placement not mapped.','Maximum requests around1.1seconds retained; p95 pass is not a uniform latency guarantee.','No product deployment/fixture install or hostile native-code isolation claim.']))
record['state']='read_target_qualified_fixture_retained_for_remaining_performance_checks';f.write(q.PRIVATE/'state.json',record)
print(json.dumps(dict(result='read_target_passed_not_full_performance_G7',requests=800,errors=0,p95_ms={name:v['p95_ms'] for name,v in metrics.items()})))
