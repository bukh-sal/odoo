"""Verify restored data, actual native schema, current authority and closed traffic."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0,str(Path(__file__).parent));import probe as p
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor

state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='restored_verified_traffic_closed'
operation=record['operation_id'];fresh=record['fresh_database'];source=record['configuration']['sites'][0]['database']
assert state['active_db']==fresh and fresh!=source
directory=native.store.root/'recoveries'/operation;result=p.load(directory/'result.json')
checkpoint=native.store.root/'checkpoints'/operation;manifest=p.load(checkpoint/'manifest.json')
decision=p.load(p.PRIVATE/'restore-payload.json')
assert native.config['generation']==decision['restore_configuration']['generation']
assert result['configuration']==native.config and result['state']=='restored_verified' and result['keep_traffic_closed']
assert result['dispatch']['profile']=='r1-reference-stateless-dispatch-v1' and result['dispatch']['control']['state']=='paused'
assert not native._inspect(state['project']+'-edge-1')['State']['Running']
status=native.store.status(operation);assert status['state']=='revoked' and status['phase']=='restore_verified' and not status['traffic_resumed']
oldlock=copy.deepcopy(manifest['previous_release']['release_lock'])
oldlock.update(generation=native.config['generation'],created_at=p.load(p.OUT/'bundle.json')['plan']['created_at'])
assert native.config['published_release']==oldlock
before=p.load(p.PRIVATE/'data-before.json');after=p.snapshot(state,'native-uninstall-current-restored-closed-data');updated=0
for table,rows in before.items():
    expected=copy.deepcopy(rows);actual=after[table];assert len(expected)==len(actual),table
    if table=='mp_workspace':
        for row in expected:row['policy_generation']+=1
    elif table=='mp_job':
        byid={row['id']:row for row in actual}
        for row in expected:
            current=byid[row['id']];changed={key for key in row if row[key]!=current[key]}
            assert changed<={'release_digest','claim_generation','dispatch_generation'},changed
            if changed:
                assert current['release_digest']==data_digest(oldlock) and current['claim_generation']==row['claim_generation']+1
                assert current['dispatch_generation']==result['dispatch']['control']['generation']
                row.update({key:current[key] for key in changed});updated+=1
    assert expected==actual,table
recovery=RestoreExecutor(native)
failed_auth,failed_private=recovery._authority(source);restored_auth,restored_private=recovery._authority(fresh)
assert failed_auth==restored_auth==decision['authority'] and failed_private==restored_private
assert p.worker(native,'native-uninstall-current-restored-closed-worker')==p.load(p.PRIVATE/'worker-before.json')
impact=p.load(p.OUT/'bundle.json')['operation_lock']['native_uninstall_impact']
program='''import configparser,json,psycopg2
from modular_platform.native_uninstall import snapshot_relations
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');o=config['options']
assert o['db_name']==DATABASE
connection=psycopg2.connect(host=o['db_host'],port=o.getint('db_port'),user=o['db_user'],password=o['db_password'],dbname=DATABASE,connect_timeout=10)
connection.set_session(isolation_level='REPEATABLE READ',readonly=True)
with connection:
 with connection.cursor() as cursor:
  cursor.execute("SET LOCAL statement_timeout='5s'")
  cursor.execute("SELECT name,latest_version FROM ir_module_module WHERE state='installed' ORDER BY name")
  versions=dict(cursor.fetchall())
 relations=snapshot_relations(connection,IMPACT)
connection.close();print(json.dumps(dict(relations=relations,versions=versions)))
'''
code='DATABASE='+repr(fresh)+'\nIMPACT='+repr(impact)+'\n'+program
native_schema=json.loads(p.f.command('native-uninstall-current-restored-native-schema',['docker','exec',native.config['worker_id'],'/venv/bin/python','-B','-c',code]))
assert native_schema['relations']==p.load(p.OUT/'native-effects.json')['before']
native_before=[]
for line in (native.store.root/'stages'/operation/'native.log').read_text(encoding='utf8').splitlines():
    try:value=json.loads(line)
    except ValueError:continue
    if isinstance(value,dict) and value.get('kind')=='native_uninstall_before':native_before.append(value)
assert len(native_before)==1 and native_schema['versions']==native_before[0]['native_versions']
files=json.loads(p.f.command('native-uninstall-current-restored-files',['docker','exec',native.config['worker_id'],'/venv/bin/python','-c',p.FILE_OBSERVATION,fresh]))
retained={};prefix='filestore/'+source+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for member in archive:
        if member.isfile() and member.name.startswith(prefix):
            retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained==p.load(p.PRIVATE/'files-before.json') and all(files.get(name)==digest for name,digest in retained.items())
secret_query="BEGIN READ ONLY;SELECT encode(sha256(convert_to(value,'UTF8')),'hex') FROM ir_config_parameter WHERE key='database.secret';ROLLBACK;"
original_state=state|dict(active_db=source)
old_digest=p.f.sql(original_state,'native-uninstall-current-failed-session-digest',secret_query).strip()
new_digest=p.f.sql(state,'native-uninstall-current-restored-session-digest',secret_query).strip()
assert old_digest and new_digest and old_digest!=new_digest
p.write(p.PRIVATE/'data-closed.json',after)
fixture=p.load(p.LOCAL/'fixtures.json');fixture['database']=fresh;p.write(p.LOCAL/'fixtures.json',fixture)
p.save('closed-preservation.json',dict(result='passed_current_native_uninstall_fresh_restore_closed',operation_id=operation,
    configuration_generation=native.config['generation'],fresh_database=fresh,failed_database_retained=source,
    checkpoint_native_relations_columns_constraints_counts_and_versions_exact=True,
    all17tables_exact_except_reviewed_workspace_security_and_terminal_job_epochs=True,terminal_job_epoch_updates=updated,
    current_native_authority_and_private_auth_exact=True,session_secret_rotated=True,technical_credentials_revoked=True,
    checkpoint_files_exact=len(retained),independent_worker_process_image_key_publication_exact=True,
    dispatch_generation=result['dispatch']['control']['generation'],dispatch_paused=True,edge_stopped=True,separate_resume_required=True,
    limits=['Actual fresh restore verified while traffic remains closed; no completed resume or generic external-effect undo claim.']))
record['closed_verified']=True;p.write(p.PRIVATE/'state.json',record);p.f.guard(state)
print(json.dumps(dict(result='fresh_restore_closed_preservation_passed',configuration=native.config['generation'],files=len(retained))),flush=True)
