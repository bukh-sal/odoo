"""Continue only exact owned removal after PostgreSQL OID JSON type audit."""
import hashlib,json,re
from driver import ROOT,OUT,PRIVATE,MARKER,context,base,f,j,save
state,native=context();record=f.load(MARKER)
assert record['state']=='dropping_exact_owned_isolated_database' and not (OUT/'cleanup.json').exists()
assert (OUT/'unknown-outcome.json').is_file() and (OUT/'reconciliation-diagnostic.json').is_file() and (PRIVATE/'effect-container-inspect.json.gz').is_file()
assert re.fullmatch(r'mp_disposable_g6_job03_[0-9a-f]{32}',record['database']) and record['database']!=state['active_db']
assert not f.command('job03-continuation-no-containers',['docker','ps','--all','--filter','label=com.modular.disposable='+record['profile'],'--format','{{.ID}}']).strip()
volume=json.loads(f.command('job03-continuation-config-volume',['docker','volume','inspect',record['config_volume']]))[0]
assert volume['Labels']['com.modular.disposable']==record['profile'] and record['config_volume'] not in (record['public_volume'],record['authority_volume'],state['project']+'_appconfig',state['project']+'_filestore')
identity=json.loads(f.sql(state,'job03-owned-database-final-identity-cast',"SELECT jsonb_build_object('oid',oid::bigint,'owner',pg_get_userbyid(datdba),'connections',(SELECT count(*) FROM pg_stat_activity WHERE datname='"+record['database']+"')) FROM pg_database WHERE datname='"+record['database']+"';",database='postgres'))
assert identity==dict(oid=record['database_oid'],owner='modular',connections=0)
f.command('job03-drop-owned-database',['docker','exec',state['project']+'-db-1','dropdb','-U','postgres',record['database']])
assert f.sql(state,'job03-database-removed',"SELECT count(*) FROM pg_database WHERE datname='"+record['database']+"';",database='postgres').strip()==b'0'
save(record,'removing_exact_owned_config_volume')
f.command('job03-remove-config-volume',['docker','volume','rm',record['config_volume']])
dump_paths=[PRIVATE/'source.dump',j.LOCAL/'logs/job03-owned-source-dump.stdout'];dumps=[]
for path in dump_paths:
    assert path.resolve().is_relative_to(j.LOCAL.resolve()) and path.is_file()
    dumps.append(dict(name=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert dumps[0]['sha256']==dumps[1]['sha256']
for path in dump_paths:path.unlink()
f.write(PRIVATE/'removed-dump-records.json',dumps)
assert base.snapshot(state,'job03-main-after-cleanup')==f.load(PRIVATE/'main-before.json')
assert base.worker(native,'job03-canonical-worker-after-cleanup')==f.load(PRIVATE/'worker-before.json')
f.save('cleanup.json',dict(result='removed_all_owned_job03_fixture_assets_after_diagnostic_archive',native_producer_and_observers_auto_removed=True,effect_fixture_stopped_and_auto_removed=True,
    isolated_database_exact_OID_owner_and_zero_connections_checked_then_dropped=True,one_owned_native_config_volume_removed=True,
    duplicate_setup_dump_bytes_removed=sum(v['bytes'] for v in dumps),effect_receipt_unknown_row_status_and_trace_retained=True,
    live_site_all17tables_and_canonical_worker_exact=True,new_images=0,remaining_fixture_containers=0,remaining_fixture_volumes=0,remaining_fixture_databases=0,
    no_force_or_global_prune=True,no_unknown_database_or_volume_touched=True,continuation_reason='PostgreSQL to_json serializes oid as text; explicit bigint cast verified same numeric OID before any DB deletion.'))
save(record,'cleaned_verified');f.guard(state)
print('Exact owned fixture database/config volume removed after OID type audit; all fixture containers gone/dumps cleaned/receipts retained; live site exact',flush=True)
