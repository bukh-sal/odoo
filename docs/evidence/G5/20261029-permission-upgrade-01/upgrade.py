"""Exact staged LIFE-05 operation, using isolated trusted fixture artifacts."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperationLocks,OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.release_staging import StageStore
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe
from restore import IDENTITIES,FULL,PLUGIN


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['stage','prepare','apply']);parser.add_argument('--operation-id');args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    target=LOCAL/'operator/target.json';config=load(target);state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json')
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1lifef99acae9d906'
    assert config['generation']==10 and config['image_id']==FULL and state['phase']=='permission_upgrade_base_ready'
    metadata=load(OUTPUT/'catalog.json');trust=ROOT/metadata['paths']['trust'];catalog_root=ROOT/metadata['paths']['catalog']
    validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True);reader=DockerObserver(config);observation=reader.read()
    before=reader.state(observation,catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));identity=json.loads(sql(reader,IDENTITIES))
    assert len(business['notes'])==4 and len(business['boards'])==2 and len(before['installations'])==6
    marker=LOCAL/'permission-upgrade.json';control=LOCAL/'operator/control';store=OperatorStore(control);executor=StagedNativeExecutor(store,target,catalog_root,validator)
    protected=[ROOT/'.local/operator/targets/g5.json',ROOT/'.local/g5-manager-upgrade/operator/target.json',ROOT/'.local/operator/trust.json',trust]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard():assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def write(name,value,folder=None):
        with ((folder or OUTPUT/'upgrade')/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    if args.action=='stage':
        folder=OUTPUT/'stage';assert not folder.exists();folder.mkdir()
        image=load(OUTPUT/'image.json')['image_id'];runtime=inspect_image(image)
        assert runtime['python_metadata']==observation['runtime']['python_metadata'],'Fixture must preserve exact approved Python runtime'
        old=observation['runtime']['inventory']['files'];new=runtime['inventory']['files']
        changed={p for p in old.keys()|new.keys() if old.get(p)!=new.get(p)}
        assert changed=={'addons/mp_example_notes_labels/__manifest__.py','artifacts/org.example.notes_labels-0.2.1.mplug','artifacts/org.example.notes_labels-0.2.2.mplug'},changed
        assert runtime['inventory']['artifacts'][PLUGIN]['digest']==load(OUTPUT/'fixture.json')['artifact_digest']
        stages=StageStore(store,config,catalog);descriptor=stages.stage(image);loaded=stages.load(descriptor);write('staged-image.json',descriptor,folder)
        with OperationLocks(store.root/'locks',config['deployment_id'],[s['site_id'] for s in config['sites']]):write('profile.json',publish_profile(reader,catalog,staged=loaded),folder)
        assert before==reader.state(reader.read(),catalog.snapshot())['state'] and business==json.loads(sql(reader,BUSINESS_SQL));guard()
        write('qualification.json',dict(result='staged_exact_fixture',image_id=image,changed_files=sorted(changed),python_runtime_exact=True,protected_hashes=hashes),folder);print(json.dumps(dict(result='staged_exact_fixture',image_id=image)));return
    op=args.operation_id;assert op
    prefix=[sys.executable,'tools/modular.py','--config',str(trust)];ops=prefix+['operations','--store',str(control)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def invoke(command):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:
            (LOCAL/('permission-upgrade-'+args.action+'.log')).write_bytes(result.stderr)
            raise RuntimeError('CLI failure: reconcile existing marker and journal; never replay')
        return json.loads(result.stdout)
    if args.action=='prepare':
        folder=OUTPUT/'upgrade';assert not folder.exists() and not marker.exists();folder.mkdir()
        record=dict(state='importing',operation_id=op,base_digest=data_digest(before),protected_hashes=hashes)
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
        code,response=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=response['data'];check_bundle(bundle,before)
        assert bundle['plan']['operation_type']=='upgrade' and len(bundle['operation_lock']['targets'])==2 and bundle['plan']['backup']['required']
        assert all(t['plugin_id']==PLUGIN and t['action']=='upgrade' for t in bundle['operation_lock']['targets'])
        assert bundle['plan']['permission_changes']==[dict(action='grant',plugin_id=PLUGIN,workspace_id=w,capability='org.example.notes:notes.write') for w in sorted(fixture['workspaces'][k]['public_id'] for k in ['A','B'])]
        assert len(bundle['plan']['artifacts'])==1 and bundle['plan']['artifacts'][0]['version']=='0.2.2' and bundle['plan']['artifacts'][0]['migration_digests']==[]
        record['plan_hash']=bundle['plan_hash'];marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        for name,value in [('bundle',bundle),('state-before',before),('business-before',business),('schema-before',schema),('identity-before',identity),('configuration-before',config),('files-before',files(reader))]:write(name+'.json',value)
        code,status=client.request('/api/v1/operations/status/'+op);assert code==200 and any(e['code']=='requested' for e in status['data']['history']);write('requested-status.json',status)
        write('registered.json',invoke(ops+['import-request',op]+options));write('independent-review.json',store.review(op,executor._validate()))
        old_hash=load(OUTPUT/'restore/bundle.json')['plan_hash'];assert old_hash!=bundle['plan_hash']
        for name,exact,ack in [('previous-plan-hash',old_hash,True),('missing-permission-ack',bundle['plan_hash'],False)]:
            try:store.approve(op,exact_hash=exact,acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=ack),revalidate=executor._validate(),noninteractive=True)
            except OperatorError as error:
                assert ('hash' in str(error).lower() if ack else 'expanded declarations require explicit acknowledgment' in str(error)),str(error)
                write(name+'.json',dict(result='denied',reason=str(error)))
            else:raise AssertionError('Invalid authority accepted: '+name)
        assert store.status(op)['state']=='awaiting_operator_approval' and before==reader.state(reader.read(),catalog.snapshot())['state'];guard()
        (LOCAL/'permission-upgrade-old-pin.json').write_text(json.dumps(dict(token=client.release_token)),encoding='utf8')
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));return
    record=load(marker);assert record['state']=='independently_reviewed_not_approved' and record['operation_id']==op and record['base_digest']==data_digest(before) and record['protected_hashes']==hashes
    assert business==load(OUTPUT/'upgrade/business-before.json') and schema==load(OUTPUT/'upgrade/schema-before.json')
    bundle=load(OUTPUT/'upgrade/bundle.json')
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions','--ack-destructive']+options))
    phase('applying');result=executor.apply(op);write('completed.json',result);assert result['state']=='completed' and result['traffic_resumed'];phase('completed_needs_verification')
    current=load(target);assert current['generation']==11 and current['image_id']==load(OUTPUT/'image.json')['image_id'] and current['worker_id']!=config['worker_id']
    after_reader=DockerObserver(current);after=after_reader.state(after_reader.read(),catalog.snapshot())['state'];actual=json.loads(sql(after_reader,BUSINESS_SQL));actual_schema=json.loads(sql(after_reader,SCHEMA))
    assert actual['notes']==business['notes'] and actual['boards']==business['boards'] and actual_schema['columns']==schema['columns'] and actual_schema['constraints']==schema['constraints']
    assert json.loads(sql(after_reader,IDENTITIES))==identity and after['bindings']==bundle['operation_lock']['bindings'] and len(after['bindings'])==10
    assert all(i['feature_state']=='enabled' and i['state']==i['metadata_state']=='installed' for i in after['installations'])
    assert [i for i in after['installations'] if i['plugin_id']!=PLUGIN]==[i for i in before['installations'] if i['plugin_id']!=PLUGIN]
    grants={g['id']:g for g in actual['grants']};assert all(grants[g['id']]==g for g in business['grants'])
    added=[g for g in actual['grants'] if g['id'] not in {r['id'] for r in business['grants']}]
    assert len(added)==2 and all(g['capability']=='org.example.notes:notes.write' and g['state']=='approved' for g in added)
    assert {g['workspace_id'] for g in added}=={fixture['workspaces'][w]['id'] for w in ['A','B']}
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-op-'+op+'-native']))[0];cmd=child['Config']['Cmd']
    assert child['State']['ExitCode']==0 and cmd[cmd.index('-u')+1]=='mp_example_notes_labels' and '-i' not in cmd
    logs=(control/'stages'/op/'native.log').read_text(encoding='utf8')+(control/'stages'/op/'native.log.stderr.log').read_text(encoding='utf8');assert 'Labels extension migration normalized' not in logs
    old_files=load(OUTPUT/'upgrade/files-before.json');now=files(after_reader);assert all(now[n]==h for n,h in old_files.items())
    checkpoint=load(control/'checkpoints'/op/'manifest.json')
    for name,digest in checkpoint['files'].items():assert hashlib.sha256((control/'checkpoints'/op/name).read_bytes()).hexdigest()==digest
    r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator');code,response=client.request('/api/v1/navigation',workspace='A',headers={'X-MP-Client-Release':load(LOCAL/'permission-upgrade-old-pin.json')['token']});assert code==409 and response['error']['code']=='CONFLICT'
    for name,value in [('state-after',after),('business-after',actual),('schema-after',actual_schema),('files-after',now),('native-upgrade',dict(arguments=cmd,native_only_labels=True,historical_migrations_absent=True)),('checkpoint-manifest',checkpoint),('old-client-rejected',response)]:write(name+'.json',value)
    write('mirror.json',invoke(ops+['mirror-status',op]+options));guard()
    state.update(phase='permission_upgrade_completed',generation=11,image_id=current['image_id'],worker_id=current['worker_id'],operator_trust_config=str(trust.relative_to(ROOT)),operator_catalog=str(catalog_root.relative_to(ROOT)))
    (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('qualification.json',dict(result='passed_actual_permission_expanding_upgrade',operation_id=op,plan_hash=record['plan_hash'],generation=11,exact_new_grants=2,old_grants_exact=True,notes_boards_schema_exact=True,stable_identities=True,old_files_preserved=len(old_files),checkpoint_hashes_verified=True,old_client_rejected=True,limits=['Browser/API/assets/protected full-state audit remain separate; G5 not complete.']))
    print(json.dumps(dict(result='completed_verified',operation_id=op,generation=11)))


if __name__=='__main__':main()
