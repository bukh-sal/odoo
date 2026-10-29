"""One live native owner, concurrent duplicate/native/feature contenders, then reinstall."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore,_write_new
from modular_platform.plans import check_bundle,data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','launch','worker','reject-stale','prepare-reinstall','reinstall']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'));marker=LOCAL/'concurrency.json';target=LOCAL/'operator/target.json'
    config=load(target);state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json')
    assert state['disposable'] and config['project']==state['project']=='mp-r0-r1lifef99acae9d906'
    assert config['image_id']=='sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea'
    catalog_root=ROOT/state['operator_catalog'];trust=ROOT/state['operator_trust_config'];validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True)
    store=OperatorStore(LOCAL/'operator/control');native=NativeExecutor(store,target,catalog_root,validator);reader=DockerObserver(config)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];ops=prefix+['operations','--store',str(store.root)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command,name):
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if r.returncode:
            (LOCAL/('concurrency-'+name+'.stderr')).write_bytes(r.stderr)
            raise RuntimeError('CLI failed; inspect exact marker/journal before any further execution')
        return json.loads(r.stdout)
    def save_state(phase,current):
        state.update(phase=phase,generation=current['generation'],worker_id=current['worker_id'],image_id=current['image_id'])
        (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    record=load(marker) if marker.exists() else dict(state='preparing',operations={})
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    def prepare_case(case,nomination,before):
        (OUTPUT/case).mkdir();client=r1_probe.Client(state,fixture,'operator')
        code,value=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});assert code==200,(code,value)
        op=value['data']['operation_id'];record['operations'][case]=dict(operation_id=op,plan_hash=value['data']['plan_hash']);phase('preparing_'+case)
        write(case+'/prepare-response.json',value)
        code,value=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=value['data'];check_bundle(bundle,before);write(case+'/bundle.json',bundle)
        code,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200;write(case+'/requested.json',value)
        write(case+'/registered.json',invoke(ops+['import-request',op]+options,'import-'+case));write(case+'/review.json',store.review(op,native._validate()))
        return bundle
    def approve(case):
        entry=record['operations'][case];write(case+'/approved.json',invoke(ops+['approve',entry['operation_id'],'--plan-hash',entry['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions','--ack-destructive']+options,'approve-'+case))
    r1_probe.r1.r0.LOCAL=LOCAL
    if args.action=='prepare':
        assert not marker.exists() and config['generation']==15 and state['phase']=='executor_crash_restored_resumed'
        before=reader.state(reader.read(),catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));assert len(business['notes'])==4 and len(business['boards'])==2 and all(n['x_notes_labels'] is None for n in business['notes'])
        phase('preparing');record['base_digest']=data_digest(before)
        for name,value in [('state-before',before),('business-before',business),('schema-before',json.loads(sql(reader,SCHEMA))),('configuration-before',config),('files-before',files(reader))]:write(name+'.json',value)
        nomination=dict(schema_version=1,operation='prepare',operation_type='uninstall',site_id=state['site_id'],plugin_id='org.example.notes_labels',workspace_ids=[],cascade=False)
        for case in ['owner','other-native']:
            bundle=prepare_case(case,nomination,before)
            assert len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==4 and bundle['plan']['backup']['required'] and bundle['plan']['destructive']
        bundle=prepare_case('other-feature',dict(nomination,operation_type='suspend',workspace_ids=[fixture['workspaces']['A']['public_id']]),before)
        assert len(bundle['operation_lock']['targets'])==1 and not bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
        assert reader.state(reader.read(),catalog.snapshot())['state']==before and json.loads(sql(reader,BUSINESS_SQL))==business
        phase('independently_reviewed_not_approved');print(json.dumps(record));return
    op=record['operations']['owner']['operation_id'];commit=LOCAL/'concurrency-commit.json'
    if args.action=='worker':
        assert record['state']=='awaiting_native_commit' and config['generation']==15
        _write_new(LOCAL/'concurrency-child.json',dict(pid=os.getpid(),operation_id=op));assert sys.stdin.buffer.read(1)==b'G'
        original=native._private_command
        def controlled(command,path,**kwargs):
            value=original(command,path,**kwargs)
            if path.name=='native.log':
                status=store.status(op);assert status['phase']=='mutation_started' and status['state']=='running'
                temporary=commit.with_suffix('.tmp');_write_new(temporary,dict(pid=os.getpid(),operation_id=op));os.replace(temporary,commit)
                if sys.stdin.buffer.read(1)!=b'R':raise OperatorError('Qualification owner lost parent after native commit; explicit recovery required')
            return value
        native._private_command=controlled;result=native.apply(op);_write_new(LOCAL/'concurrency-worker-result.json',result);return
    if args.action=='launch':
        assert record['state']=='independently_reviewed_not_approved' and config['generation']==15 and not commit.exists()
        for report in ['source-host.json','source-linux.json']:
            value=load(OUTPUT/report);assert value['result']=='passed' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in value['source_sha256'].items())
        assert record['base_digest']==data_digest(reader.state(reader.read(),catalog.snapshot())['state'])
        for case in ['owner','other-native','other-feature']:approve(case)
        phase('awaiting_native_commit')
        with (LOCAL/'concurrency-worker.stdout').open('xb') as stdout,(LOCAL/'concurrency-worker.stderr').open('xb') as stderr:
            process=subprocess.Popen([sys._base_executable,'-X','utf8',str(Path(__file__).resolve()),'worker'],cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'.venv/Lib/site-packages')),stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
            _write_new(LOCAL/'concurrency-spawn.json',dict(pid=process.pid,parent_pid=os.getpid(),operation_id=op))
            def wait_file(path,seconds):
                deadline=time.monotonic()+seconds
                while not path.exists():
                    if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Owner observation failed; reconcile live handle/journal, never relaunch')
                    time.sleep(.2)
                return load(path)
            assert wait_file(LOCAL/'concurrency-child.json',30)['pid']==process.pid
            process.stdin.write(b'G');process.stdin.flush()
            assert wait_file(commit,420)['pid']==process.pid and process.poll() is None
            status=store.status(op);assert status['state']=='running' and status['phase']=='mutation_started' and not status['traffic_resumed']
            assert next(e['details']['executor_pid'] for e in status['history'] if e['code']=='reserved')==process.pid
            child=inspect(config['project']+'-op-'+op+'-native');assert not child['State']['Running'] and child['State']['ExitCode']==0
            snapshots={case:store.status(entry['operation_id']) for case,entry in record['operations'].items()}
            def contend(case):
                ident=record['operations']['owner' if case=='duplicate-owner' else case]['operation_id']
                r=subprocess.run(prefix+['plugin','apply',ident,'--store',str(store.root)]+options,cwd=ROOT,capture_output=True,timeout=120)
                (LOCAL/('concurrency-'+case+'.stderr')).write_bytes(r.stderr)
                assert r.returncode!=0 and b'Another executor holds the process lock; no takeover is allowed' in r.stderr
                return dict(case=case,operation_id=ident,exit_code=r.returncode,result='rejected_live_process_lock')
            with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(contend,['duplicate-owner','other-native','other-feature']))
            assert all(store.status(entry['operation_id'])==snapshots[case] for case,entry in record['operations'].items())
            for case in ['other-native','other-feature']:
                ident=record['operations'][case]['operation_id'];assert not (store.root/'stages'/ident).exists()
                assert subprocess.run(['docker','inspect',config['project']+'-op-'+ident+('-feature' if case=='other-feature' else '-native')],capture_output=True).returncode!=0
            assert load(target)==config
            write('contention.json',dict(result='passed',owner_pid=process.pid,owner_operation_id=op,native_child_id=child['Id'],native_child_exit_code=0,owner_phase='mutation_started',owner_live_after_contenders=process.poll() is None,all_journals_unchanged=True,no_contender_stages_or_children=True,contenders=results))
            phase('contenders_rejected_owner_continuing');process.stdin.write(b'R');process.stdin.flush();process.communicate(timeout=420);assert process.returncode==0,'Reconcile native journal before any other action'
        completed=store.status(op);assert completed['state']=='completed' and completed==load(LOCAL/'concurrency-worker-result.json')
        write('owner/completed.json',completed);current=load(target);assert current['generation']==16 and current['worker_id']!=config['worker_id'] and current['image_id']==config['image_id']
        after=DockerObserver(current);actual=json.loads(sql(after,BUSINESS_SQL));before=load(OUTPUT/'business-before.json')
        assert actual['notes']==[{k:v for k,v in n.items() if k!='x_notes_labels'} for n in before['notes']] and actual['boards']==before['boards']
        write('owner/state-after.json',after.state(after.read(),catalog.snapshot())['state']);write('owner/business-after.json',actual);write('owner/schema-after.json',json.loads(sql(after,SCHEMA)));write('owner/configuration-after.json',current)
        save_state('concurrency_labels_uninstalled',current);phase('owner_completed_contenders_pending_retirement');print(json.dumps(dict(state=record['state'],operation_id=op,generation=16)));return
    if args.action=='reject-stale':
        assert record['state']=='owner_completed_contenders_pending_retirement' and config['generation']==16
        current=reader.state(reader.read(),catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));results=[]
        for case in ['other-native','other-feature']:
            ident=record['operations'][case]['operation_id'];old=store.status(ident)
            r=subprocess.run(prefix+['plugin','apply',ident,'--store',str(store.root)]+options,cwd=ROOT,capture_output=True,timeout=120)
            (LOCAL/('concurrency-stale-'+case+'.stderr')).write_bytes(r.stderr)
            assert r.returncode!=0 and b'Stale plan: deployment state or generation changed' in r.stderr and store.status(ident)==old
            assert not (store.root/'stages'/ident).exists();store.revoke(ident);write(case+'/revoked.json',store.status(ident));results.append(dict(case=case,operation_id=ident,result='stale_base_refused_before_reservation_then_revoked'))
        old=store.status(op);replay=invoke(prefix+['plugin','apply',op,'--store',str(store.root)]+options,'completed-replay');assert replay==old and store.status(op)==old;write('owner/completed-replay.json',replay)
        assert current==reader.state(reader.read(),catalog.snapshot())['state'] and business==json.loads(sql(reader,BUSINESS_SQL))
        write('stale-and-completed-replay.json',dict(result='passed',contenders=results,completed_owner_exact_saved_result=True,no_repeat_native_or_metadata=True))
        phase('contenders_retired_ready_reinstall');print(json.dumps(dict(state=record['state'])));return
    if args.action=='prepare-reinstall':
        assert record['state']=='contenders_retired_ready_reinstall' and config['generation']==16
        before=reader.state(reader.read(),catalog.snapshot())['state'];artifact=next(p for p in before['release_lock']['plugins'] if p['plugin_id']=='org.example.notes_labels')
        nomination=dict(schema_version=1,operation='prepare',operation_type='install',site_id=state['site_id'],plugin_id=artifact['plugin_id'],artifact_version=artifact['version'],artifact_digest=artifact['digest'],workspace_ids=[fixture['workspaces'][k]['public_id'] for k in ['A','B']],cascade=False)
        bundle=prepare_case('reinstall',nomination,before);assert len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==4 and bundle['plan']['backup']['required']
        assert {f['availability'] for f in bundle['operation_lock']['feature_states']}=={'enabled'} and 'staged_image' not in bundle['operation_lock']
        write('reinstall/state-before.json',before);phase('reinstall_independently_reviewed_not_approved');print(json.dumps(record['operations']['reinstall']));return
    assert args.action=='reinstall' and record['state']=='reinstall_independently_reviewed_not_approved' and config['generation']==16
    approve('reinstall');phase('reinstalling_exact_reviewed_plan');ident=record['operations']['reinstall']['operation_id']
    result=invoke(prefix+['plugin','apply',ident,'--store',str(store.root)]+options,'reinstall');write('reinstall/completed.json',result);assert result['state']=='completed'
    current=load(target);assert current['generation']==17 and current['image_id']==config['image_id']
    after=DockerObserver(current);actual=json.loads(sql(after,BUSINESS_SQL));observed=after.state(after.read(),catalog.snapshot())['state'];before=load(OUTPUT/'business-before.json')
    assert actual['notes']==before['notes'] and actual['boards']==before['boards'] and json.loads(sql(after,SCHEMA))==load(OUTPUT/'schema-before.json')
    assert observed['installations']==load(OUTPUT/'state-before.json')['installations'] and observed['bindings']==load(OUTPUT/'state-before.json')['bindings']
    normalize=lambda rows:[{k:v for k,v in row.items() if k not in ('write_date','write_uid')} for row in rows]
    for key in ['features','grants']:assert normalize(actual[key])==normalize(before[key]),key
    # Native uninstall deletes affected binding rows. Reinstall preserves their
    # public identities/descriptors while allocating fresh internal row IDs.
    public_bindings=lambda rows:{r['public_id']:{k:v for k,v in r.items() if k not in ('id','create_date','write_date','write_uid')} for r in rows}
    assert public_bindings(actual['bindings'])==public_bindings(before['bindings'])
    now=files(after);assert all(now[n]==h for n,h in load(OUTPUT/'files-before.json').items())
    child=inspect(config['project']+'-op-'+ident+'-native');assert child['State']['ExitCode']==0 and '-i' in child['Config']['Cmd'] and '-u' not in child['Config']['Cmd']
    write('reinstall/native-initialization.json',dict(arguments=child['Config']['Cmd'],exit_code=0))
    for name,value in [('state-after',observed),('business-after',actual),('schema-after',json.loads(sql(after,SCHEMA))),('configuration-after',current),('files-after',now)]:write(name+'.json',value)
    save_state('concurrency_restored_all_enabled',current);phase('completed_verified');print(json.dumps(dict(state=record['state'],generation=17)))


def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]


if __name__=='__main__':main()
