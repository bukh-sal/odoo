"""Archive unknown/effect diagnostics, then remove only exact owned fixture assets."""
import gzip,hashlib,json,re,subprocess
from pathlib import Path
from driver import ROOT,OUT,PRIVATE,MARKER,context,base,f,j,receipt,inspect,save
from datetime import datetime,timezone

state,native=context();record=f.load(MARKER);assert record['state']=='qualified_needs_cleanup' and not (OUT/'cleanup.json').exists()
assert re.fullmatch(r'mp_disposable_g6_job03_[0-9a-f]{32}',record['database']) and record['database']!=state['active_db']
assert record['config_volume'] not in (record['public_volume'],record['authority_volume'],state['project']+'_appconfig',state['project']+'_filestore')
remote=receipt(record);assert remote==f.load(PRIVATE/'external-receipt-before-kill.json') and remote['count']==1
row=f.load(PRIVATE/'row-before-kill.json');deadline=datetime.fromisoformat(row['deadline_at']).replace(tzinfo=timezone.utc)
first_observer=j.LOCAL/'logs/job03-observe-native.stderr';ended=datetime.fromtimestamp(first_observer.stat().st_mtime,timezone.utc)
assert ended<deadline and row['max_attempts']==3 and row['attempts']==1
f.save('retry-budget-proof.json',dict(result='original_reclaimer_reached_unknown_with_retry_budget_remaining',first_observer_ended_UTC=ended.isoformat(),original_job_deadline_UTC=deadline.isoformat(),max_attempts=3,attempts=1,
    first_observer_native_status_assertions_passed_before_operator_isolation_error=True,real_lease_not_modified=True,first_observer_diagnostics_sha256=hashlib.sha256(first_observer.read_bytes()).hexdigest()))
unknown=f.load(PRIVATE/'unknown-row.json');assert unknown['state']=='outcome_unknown' and unknown['attempts']==1 and unknown['effect_started']
f.save('reconciliation-diagnostic.json',dict(result='external_effect_requires_explicit_reconciliation',job_id=record['job_id'],native_job_state='outcome_unknown',error_code='LEASE_EXPIRED',effect_started=True,attempts=1,remote_receipt=remote,
    safe_operator_action='Do not retry or claim rollback. Independently compare operation ID/input receipt and perform effect-specific reconciliation before a new deployment/resume approval.',automatic_dispatch_resume_allowed=False,
    test_fixture_only=True,unknown_row_and_original_trace_archived_privately=True))
info=inspect(record['effect_container']);assert info['Config']['Labels']['com.modular.disposable']==record['profile'] and info['Image']==record['effect_image'] and info['State']['Running']
with gzip.open(PRIVATE/'effect-container-inspect.json.gz','xb') as stream:stream.write(json.dumps(info).encode())
volume=json.loads(f.command('job03-config-volume-before-cleanup',['docker','volume','inspect',record['config_volume']]))[0]
assert volume['Labels']['com.modular.disposable']==record['profile']
control=json.loads(f.sql(state,'job03-final-isolated-control',"BEGIN READ ONLY;SELECT jsonb_build_object('state',state,'generation',generation) FROM mp_dispatch_control;ROLLBACK;",database=record['database']))
assert control['state']=='paused';f.write(PRIVATE/'isolated-control-final.json',control)
save(record,'stopping_exact_effect_fixture')
f.command('job03-stop-effect',['docker','stop','--time','10',record['effect_container']],timeout=20)
remaining=f.command('job03-owned-containers-after-stop',['docker','ps','--all','--filter','label=com.modular.disposable='+record['profile'],'--format','{{.ID}}']).strip();assert not remaining
save(record,'dropping_exact_owned_isolated_database')
identity=json.loads(f.sql(state,'job03-owned-database-final-identity',"SELECT jsonb_build_object('oid',oid::bigint,'owner',pg_get_userbyid(datdba),'connections',(SELECT count(*) FROM pg_stat_activity WHERE datname='"+record['database']+"')) FROM pg_database WHERE datname='"+record['database']+"';",database='postgres'))
assert identity==dict(oid=record['database_oid'],owner='modular',connections=0)
f.command('job03-drop-owned-database',['docker','exec',state['project']+'-db-1','dropdb','-U','postgres',record['database']])
assert f.sql(state,'job03-database-removed',"SELECT count(*) FROM pg_database WHERE datname='"+record['database']+"';",database='postgres').strip()==b'0'
save(record,'removing_exact_owned_config_volume')
f.command('job03-remove-config-volume',['docker','volume','rm',record['config_volume']])
# Remove two known duplicate setup dumps, retaining digest/size and bounded
# receipts/status/row diagnostics. Never enumerate or recursively delete paths.
dump_paths=[PRIVATE/'source.dump',j.LOCAL/'logs/job03-owned-source-dump.stdout'];dump_records=[]
for path in dump_paths:
    resolved=path.resolve();assert resolved.is_relative_to(j.LOCAL.resolve()) and resolved.is_file()
    dump_records.append(dict(name=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert dump_records[0]['sha256']==dump_records[1]['sha256']
for path in dump_paths:path.unlink()
f.write(PRIVATE/'removed-dump-records.json',dump_records)
assert base.snapshot(state,'job03-main-after-cleanup')==f.load(PRIVATE/'main-before.json')
assert base.worker(native,'job03-canonical-worker-after-cleanup')==f.load(PRIVATE/'worker-before.json')
f.save('cleanup.json',dict(result='removed_all_owned_job03_fixture_assets_after_diagnostic_archive',native_producer_and_observers_auto_removed=True,effect_fixture_stopped_and_auto_removed=True,
    isolated_database_exact_OID_owner_and_zero_connections_checked_then_dropped=True,one_owned_native_config_volume_removed=True,
    duplicate_setup_dump_bytes_removed=sum(r['bytes'] for r in dump_records),effect_receipt_unknown_row_status_and_trace_retained=True,
    live_site_all17tables_and_canonical_worker_exact=True,new_images=0,remaining_fixture_containers=0,remaining_fixture_volumes=0,remaining_fixture_databases=0,
    no_force_or_global_prune=True,no_unknown_database_or_volume_touched=True))
save(record,'cleaned_verified');f.guard(state)
print('All isolated JOB03 containers/database/config volume and duplicate dumps cleaned; unknown/effect receipts archived; live site/worker exact',flush=True)
