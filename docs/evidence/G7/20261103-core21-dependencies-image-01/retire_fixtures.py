"""Archive and retire only completed, explicitly owned compatibility fixtures."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core21-fresh-registry-01'
state=json.loads((PRIVATE/'state.json').read_text());assert state['state']=='fresh_core_native_login_assets_passed_http_server_retired'
def call(label,args,raw=None,timeout=120):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=raw,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect exact '+label+'; no repeated deletion/mutation'
 return (PRIVATE/(label+'.stdout')).read_bytes()
def sql(label,query,database='postgres'):return call(label,['docker','exec','-i',state['shared_pg'],'psql','-X','-qAt','-U','postgres','-d',database,'-v','ON_ERROR_STOP=1'],query.encode())
tables='mp_example_note mp_example_canvas_board mp_example_note_event_summary mp_plugin_installation mp_workspace_plugin mp_service_binding mp_plugin_grant mp_service_credential mp_workspace mp_membership mp_principal mp_outbox mp_event_subscription mp_event_delivery mp_event_consumption mp_event_consumer_state mp_job'.split()
query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT encode(sha256(convert_to(jsonb_build_object("+','.join("'"+n+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+n+" t),'[]'::jsonb)" for n in tables)+")::text,'UTF8')),'hex'); ROLLBACK;"
assert sql('retirement-source-before',query,state['source_database']).strip().decode()==(PRIVATE/'source-before.stdout').read_text().strip()
owner=sql('retirement-db-owner',"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+state['database']+"';").strip().decode()
assert owner==(PRIVATE/'source-owner.stdout').read_text().strip()
assert sql('retirement-db-no-sessions',"SELECT count(*) FROM pg_stat_activity WHERE datname='"+state['database']+"';").strip()==b'0'
vol=json.loads(call('retirement-volume-inspect',['docker','volume','inspect',state['volume']]))[0]
assert vol['Labels']['com.modular.disposable']==state['project']
assert not call('retirement-volume-users',['docker','ps','-aq','--filter','volume='+state['volume']]).strip()
dump=call('fresh-core-archive',['docker','exec',state['shared_pg'],'pg_dump','-U','postgres','-Fc',state['database']]);assert dump.startswith(b'PGDMP')
assert b'TABLE' in call('fresh-core-archive-verify',['docker','exec','-i',state['shared_pg'],'pg_restore','--list'],dump)
archive_code="import pathlib,sys,tarfile;root=pathlib.Path('/probe');assert not any(p.is_symlink() for p in root.rglob('*'));t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz');t.add(root,arcname='fresh-config-data');t.close()"
archive=call('fresh-volume-archive',['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+state['volume']+',target=/probe,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-B','-c',archive_code])
entries=[]
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
 for member in tar:
  assert not member.name.startswith('/') and '..' not in member.name.split('/') and not member.issym() and not member.islnk()
  if member.isfile():
   raw=tar.extractfile(member).read();assert len(raw)==member.size;entries.append(dict(path=member.name,size=member.size,sha256=hashlib.sha256(raw).hexdigest()))
assert entries
call('retire-owned-fresh-database',['docker','exec',state['shared_pg'],'dropdb','-U','postgres',state['database']])
assert sql('retirement-db-absent',"SELECT count(*) FROM pg_database WHERE datname='"+state['database']+"';").strip()==b'0'
call('retire-owned-fresh-volume',['docker','volume','rm',state['volume']])
probe_path=ROOT/'.local/g7-dependency-compatibility-01/probe-state.json';probe=json.loads(probe_path.read_text())
assert probe['state']=='primitive_compatibility_qualified_helpers_retired_probe_retained'
v=json.loads(call('old-probe-volume-inspect',['docker','volume','inspect',probe['volume']]))[0];assert v['Labels']['com.modular.disposable']==probe['project']
assert not call('old-probe-volume-users',['docker','ps','-aq','--filter','volume='+probe['volume']]).strip()
check="import json,pathlib;root=pathlib.Path('/probe');names={p.name for p in root.iterdir()};assert names=={'venv','wheels','ldap-wheel','probe-requirements.lock'},names;print(json.dumps(dict(root_entries=sorted(names),binary_environment_only=True)))"
probe_root=json.loads(call('old-probe-root-check',['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+probe['volume']+',target=/probe,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-B','-c',check]))
call('retire-redundant-probe-volume',['docker','volume','rm',probe['volume']])
for name in [state['volume'],probe['volume']]:
 r=subprocess.run(['docker','volume','inspect',name],capture_output=True,timeout=30);assert r.returncode!=0 and b'no such' in r.stderr.lower()
assert sql('retirement-source-after',query,state['source_database']).strip().decode()==(PRIVATE/'source-before.stdout').read_text().strip()
old=json.loads((PRIVATE/'worker-before.stdout').read_text())[0];new=json.loads(call('retirement-worker-after',['docker','inspect','--type','container',old['Id']]))[0]
assert new['State']['Running'] and new['State']['StartedAt']==old['State']['StartedAt'] and all(new[k]==old[k] for k in ['Image','RestartCount'])
state['state']='fresh_native_http_qualified_archived_fixture_retired';(PRIVATE/'state.json').write_text(json.dumps(state,indent=2)+'\n')
probe['state']='retired_replaced_by_actual_core21_image';probe['replacement_image_id']=state['image_id'];probe_path.write_text(json.dumps(probe,indent=2)+'\n')
report=dict(result='retired_completed_owned_fixtures',database=state['database'],removed_volumes=[state['volume'],probe['volume']],
 fresh_database_archive=dict(sha256=hashlib.sha256(dump).hexdigest(),bytes=len(dump),pg_restore_list_verified=True),fresh_volume_archive=dict(sha256=hashlib.sha256(archive).hexdigest(),bytes=len(archive),entries=len(entries),all_entries_read_hash_verified=True),
 old_probe=probe_root,old_probe_reconstruction='Original protected31 image plus all verified downloaded wheels/LDAP wheel, metadata/hashes and install diagnostics retained privately; no database/user data in binary-only probe.',
 original_17tables_worker_exact=True,candidate_image_retained_for_actual_maintenance=state['image_id'],no_unknown_or_shared_resources_removed=True)
with (OUT/'retirement.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],volumes=2,databases=1,original_preserved=True)))
