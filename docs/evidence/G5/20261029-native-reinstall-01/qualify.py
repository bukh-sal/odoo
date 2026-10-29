"""Existing browser requests: one-workspace reinstall, then explicit grant enable.

No bootstrap, automatic request replay, schema patch or alternative executor.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local/g5-lifecycle'
sys.path[:0] = [str(ROOT / 'packages/platform_sdk'), str(ROOT / 'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle, data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql
from qualify_manager_upgrade_operation import files
import r1_probe


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare','apply'])
    parser.add_argument('--case', required=True, choices=['reinstall-A','enable-B']); parser.add_argument('--operation-id', required=True)
    args = parser.parse_args(); reinstall = args.case == 'reinstall-A'; op = args.operation_id
    target = LOCAL / 'operator/target.json'; marker = LOCAL / (args.case + '.json'); output = OUTPUT / args.case
    config = json.loads(target.read_text(encoding='utf8')); state = json.loads((LOCAL / 'state.json').read_text(encoding='utf8'))
    fixture = json.loads((LOCAL / 'fixtures.json').read_text(encoding='utf8'))
    assert state['disposable'] and state['phase'] == ('labels_uninstalled' if reinstall else 'labels_reinstalled_A')
    assert config['project'] == state['project'] == 'mp-r0-r1lifef99acae9d906' and config['generation'] == (5 if reinstall else 6)
    protected = [ROOT / '.local/operator/targets/g5.json', ROOT / '.local/g5-manager-upgrade/operator/target.json']
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard(): assert hashes == {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    validator = configuration(ROOT / '.local/operator/trust.json'); catalog_root = ROOT / '.local/operator/catalog'
    catalog = Catalog(catalog_root, validator, readonly=True).snapshot(); reader = DockerObserver(config)
    before = reader.state(reader.read(), catalog)['state']; business = json.loads(sql(reader, BUSINESS_SQL)); schema = json.loads(sql(reader, SCHEMA))
    r1_probe.r1.r0.LOCAL = LOCAL; operator = r1_probe.Client(state, fixture, 'operator')
    code, response = operator.request('/api/v1/operations/bundle/' + op); assert code == 200
    bundle = response['data']; check_bundle(bundle,before); exact_hash = bundle['plan_hash']; lock = bundle['operation_lock']
    expected_workspace = fixture['workspaces']['A' if reinstall else 'B']['public_id']
    assert bundle['plan']['operation_type'] == ('install' if reinstall else 'enable')
    assert len(lock['targets']) == (2 if reinstall else 1) and all(t['plugin_id']=='org.example.notes_labels' for t in lock['targets'])
    assert len(bundle['plan']['permission_changes']) == 1
    change = bundle['plan']['permission_changes'][0]
    assert change['action']=='grant' and change['workspace_id']==expected_workspace and change['capability']=='org.example.notes:notes.read'
    if reinstall:
        assert bundle['plan']['backup']['required'] and all(a['migration_digests']==[] for a in bundle['plan']['artifacts'])
        assert {f['workspace_id']:f['availability'] for f in lock['feature_states']} == {
            fixture['workspaces']['A']['public_id']:'enabled',fixture['workspaces']['B']['public_id']:'suspended'}
        assert 'staged_image' not in lock
    else:
        assert lock['targets'][0]['workspace_id']==expected_workspace and not bundle['plan']['backup']['required']
        assert bundle['plan']['target_release_digest']==before['release_digest'] and lock['bindings']==before['bindings']
    control=LOCAL/'operator/control'; store=OperatorStore(control); native=NativeExecutor(store,target,catalog_root,validator)
    prefix=[sys.executable,'tools/modular.py','--config',str(ROOT/'.local/operator/trust.json')]
    ops=prefix+['operations','--store',str(control)]; options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def write(name,value):
        with (output/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:
            (LOCAL/(args.case+'-cli-'+args.action+'.log')).write_bytes(result.stderr)
            raise RuntimeError('CLI failure: inspect existing marker/journal; never blind replay')
        return json.loads(result.stdout)
    if args.action=='prepare':
        assert not marker.exists() and not output.exists(); output.mkdir()
        record=dict(state='importing',operation_id=op,plan_hash=exact_hash,base_digest=data_digest(before),protected_config_hashes=hashes)
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        write('bundle.json',bundle);write('state-before.json',before);write('business-before.json',business);write('schema-before.json',schema)
        write('files-before.json',files(reader));write('configuration-before.json',config)
        write('identity-rows-before.json',json.loads(sql(reader,"SELECT jsonb_build_object('installations',(SELECT jsonb_agg(jsonb_build_array(id,public_id,plugin_id) ORDER BY id) FROM mp_plugin_installation),'scopes',(SELECT jsonb_agg(jsonb_build_array(id,workspace_id,plugin_id,installation_id) ORDER BY id) FROM mp_workspace_plugin));")))
        code,status=operator.request('/api/v1/operations/status/'+op)
        assert code==200 and any(e['code']=='requested' for e in status['data']['history'])
        write('requested-status.json',status['data']);write('registered.json',invoke(ops+['import-request',op]+options))
        write('independent-review.json',store.review(op,native._validate()))
        try:
            store.approve(op,exact_hash=exact_hash,acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=False),revalidate=native._validate(),noninteractive=True)
        except Exception as error:
            assert 'expanded declarations require explicit acknowledgment' in str(error),type(error).__name__
            write('missing-permission-ack.json',dict(result='denied',reason=str(error)))
        else:raise AssertionError('Permission expansion without acknowledgment accepted')
        assert store.status(op)['state']=='awaiting_operator_approval' and before==reader.state(reader.read(),catalog)['state'];guard()
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf8'))
    assert record['state']=='independently_reviewed_not_approved' and record['operation_id']==op and record['base_digest']==data_digest(before)
    assert record['protected_config_hashes']==hashes and business==json.loads((output/'business-before.json').read_text(encoding='utf8'))
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',exact_hash,'--noninteractive','--ack-trust','--ack-permissions','--ack-destructive']+options))
    phase('applying');status=invoke(prefix+['plugin','apply',op,'--store',str(control)]+options);write('completed.json',status)
    assert status['state']=='completed';phase('completed_needs_verification')
    current=json.loads(target.read_text(encoding='utf8'));after_reader=DockerObserver(current);after=after_reader.state(after_reader.read(),catalog)['state']
    actual=json.loads(sql(after_reader,BUSINESS_SQL));actual_schema=json.loads(sql(after_reader,SCHEMA))
    assert [{k:v for k,v in n.items() if k!='x_notes_labels'} for n in actual['notes']]==[{k:v for k,v in n.items() if k!='x_notes_labels'} for n in business['notes']]
    assert actual['boards']==business['boards'] and len(after['installations'])==6 and len(after['bindings'])==10
    labels=[i for i in after['installations'] if i['plugin_id']=='org.example.notes_labels']
    assert all(i['state']==i['metadata_state']=='installed' for i in labels)
    assert {i['workspace_id']:i['feature_state'] for i in labels}=={
        fixture['workspaces']['A']['public_id']:'enabled',fixture['workspaces']['B']['public_id']:('suspended' if reinstall else 'enabled')}
    identity=json.loads(sql(after_reader,"SELECT jsonb_build_object('installations',(SELECT jsonb_agg(jsonb_build_array(id,public_id,plugin_id) ORDER BY id) FROM mp_plugin_installation),'scopes',(SELECT jsonb_agg(jsonb_build_array(id,workspace_id,plugin_id,installation_id) ORDER BY id) FROM mp_workspace_plugin));"))
    assert identity==json.loads((output/'identity-rows-before.json').read_text(encoding='utf8'))
    labels_id=int(sql(after_reader,"SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels';"))
    grants=[g for g in actual['grants'] if g['installation_id']==labels_id]
    assert len(grants)==2 and {g['workspace_id']:g['state'] for g in grants}=={fixture['workspaces']['A']['id']:'approved',fixture['workspaces']['B']['id']:('revoked' if reinstall else 'approved')}
    if reinstall:
        assert current['generation']==6 and current['image_id']==config['image_id'] and current['worker_id']!=config['worker_id']
        child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-op-'+op+'-native']))[0]
        assert child['State']['ExitCode']==0 and '-i' in child['Config']['Cmd'] and '-u' not in child['Config']['Cmd']
        log=(control/'stages'/op/'native.log.stderr.log').read_text(encoding='utf8')+(control/'stages'/op/'native.log').read_text(encoding='utf8')
        assert 'Labels extension migration normalized' not in log
        write('native-initialization.json',dict(arguments=child['Config']['Cmd'],exit_code=0,current_version='0.2.1',historical_migration_log_absent=True))
    else:
        assert current==config and after['release_digest']==before['release_digest'] and actual_schema==schema
    old_files=json.loads((output/'files-before.json').read_text(encoding='utf8'));now_files=files(after_reader)
    assert all(now_files[name]==digest for name,digest in old_files.items())
    write('state-after.json',after);write('business-after.json',actual);write('schema-after.json',actual_schema);write('files-after.json',now_files)
    write('completed-mirror.json',invoke(ops+['mirror-status',op]+options));guard()
    state.update(phase=('labels_reinstalled_A' if reinstall else 'lifecycle_reinstalled_all_enabled'),generation=6,image_id=current['image_id'],worker_id=current['worker_id'])
    (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('qualification.json',dict(result='passed_'+args.case,operation_id=op,plan_hash=exact_hash,generation=6,stable_installation_scope_row_identities=True,
          exact_scoped_availability_and_grants=True,note_board_identity_content_revision_preserved=True,old_files_preserved=len(old_files),protected_config_hashes=hashes,
          limits=['HTTP/UI scoped gate regression remains separate; artifact removal and upgrade permission expansion remain required.']))
    print(json.dumps(dict(result='passed_'+args.case,operation_id=op,generation=6)))


if __name__=='__main__':main()
