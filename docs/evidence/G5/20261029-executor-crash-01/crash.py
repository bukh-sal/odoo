"""Kill the actual lock-holding executor after its native child committed."""
import argparse
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
from modular_platform.unchanged_recovery import UnchangedReleaseRecovery
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe


def main():
    global OUTPUT
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','launch','worker','reconcile','reconcile-launcher']);parser.add_argument('--operation-id');parser.add_argument('--run',choices=['01','02'],default='01');args=parser.parse_args()
    qualification_root=OUTPUT
    if args.run=='02':OUTPUT=OUTPUT/'attempt02'
    stem='executor-crash'+('02' if args.run=='02' else '')
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    target=LOCAL/'operator/target.json';config=load(target);state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');marker=LOCAL/(stem+'.json');commit=LOCAL/(stem+'-commit.json')
    generation=11 if args.run=='01' else 13
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==generation
    assert config['image_id']=='sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea'
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True)
    store=OperatorStore(LOCAL/'operator/control');reader=DockerObserver(config);native=NativeExecutor(store,target,catalog_root,validator)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];ops=prefix+['operations','--store',str(store.root)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command):
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if r.returncode:
            (LOCAL/('executor-crash-'+args.action+'.log')).write_bytes(r.stderr)
            raise RuntimeError('CLI failed; reconcile exact marker, journal and process before any next action')
        return json.loads(r.stdout)
    if args.action=='prepare':
        assert state['phase']==('premutation_unchanged_resumed' if args.run=='01' else 'executor_crash_restored_resumed') and not marker.exists()
        if args.run=='02':assert load(LOCAL/'executor-crash.json')['state']=='completed_verified' and not OUTPUT.exists();OUTPUT.mkdir()
        before=reader.state(reader.read(),catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
        assert len(business['notes'])==4 and len(business['boards'])==2 and len(before['installations'])==6 and len(before['bindings'])==10
        record=dict(state='preparing',base_digest=data_digest(before));marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        for name,value in [('state-before',before),('business-before',business),('schema-before',schema),('configuration-before',config),('files-before',files(reader))]:write(name+'.json',value)
        r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
        nomination=dict(schema_version=1,operation='prepare',operation_type='uninstall',site_id=state['site_id'],plugin_id='org.example.notes_labels',workspace_ids=[],cascade=False)
        code,value=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});write('prepare-response.json',dict(status=code,response=value));assert code==200
        op=value['data']['operation_id'];code,value=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=value['data'];check_bundle(bundle,before)
        assert len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==4 and bundle['plan']['destructive'] and bundle['plan']['backup']['required']
        assert all(a['version']=='0.2.2' for a in bundle['plan']['artifacts']);write('bundle.json',bundle)
        record.update(operation_id=op,plan_hash=bundle['plan_hash'],state='importing');marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        code,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200;write('requested.json',value)
        write('registered.json',invoke(ops+['import-request',op]+options));write('independent-review.json',store.review(op,native._validate()))
        assert before==reader.state(reader.read(),catalog.snapshot())['state'] and business==json.loads(sql(reader,BUSINESS_SQL))
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));return
    record=load(marker);op=record['operation_id']
    def phase(value,**extra):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat(),**extra);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    if args.action=='worker':
        assert args.operation_id==op and record['state']=='awaiting_native_commit' and not commit.exists()
        started=LOCAL/(stem+'-child.json');temporary=started.with_suffix('.tmp')
        _write_new(temporary,dict(operation_id=op,pid=os.getpid()));os.replace(temporary,started)
        assert sys.stdin.buffer.read(1)==b'G','Parent must verify the actual interpreter PID before execution'
        original=native._private_command
        def checkpointed_child(command,path,**kwargs):
            result=original(command,path,**kwargs)
            if path.name=='native.log':
                status=store.status(op);assert status['mutation_started'] and status['phase']=='mutation_started' and not status['traffic_resumed']
                temporary=commit.with_suffix('.tmp');_write_new(temporary,dict(operation_id=op,executor_pid=os.getpid(),native_log_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                os.replace(temporary,commit)
                # Only this spawned parent's OS kill releases the executor's
                # live locks. EOF is a conservative failure, never a fake crash.
                sys.stdin.buffer.read(1)
                raise OperatorError('Qualification parent disappeared after possible native commit; reconcile')
            return result
        native._private_command=checkpointed_child;native.apply(op);raise AssertionError('Crash worker unexpectedly completed')
    if args.action=='launch':
        assert record['state']=='independently_reviewed_not_approved' and not commit.exists() and not (LOCAL/(stem+'-spawn.json')).exists()
        for name in ['source-host2.json','source-linux4.json','source-freeze.json']:
            report=load(qualification_root/name);assert report['result']=='passed'
            assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['source_sha256'].items())
        assert config==load(OUTPUT/'configuration-before.json') and record['base_digest']==data_digest(reader.state(reader.read(),catalog.snapshot())['state'])
        phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+options))
        phase('awaiting_native_commit')
        with (LOCAL/(stem+'-worker.stdout.log')).open('xb') as stdout,(LOCAL/(stem+'-worker.stderr.log')).open('xb') as stderr:
            env=dict(os.environ,PYTHONPATH=str(ROOT/'.venv/Lib/site-packages'))
            process=subprocess.Popen([sys._base_executable,'-X','utf8',str(Path(__file__).resolve()),'worker','--run',args.run,'--operation-id',op],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
            _write_new(LOCAL/(stem+'-spawn.json'),dict(operation_id=op,executor_pid=process.pid,parent_pid=os.getpid(),direct_base_interpreter=True))
            started=LOCAL/(stem+'-child.json');start_deadline=time.monotonic()+30
            while not started.exists():
                if process.poll() is not None or time.monotonic()>start_deadline:raise RuntimeError('Executor startup not verified; reconcile before any execution')
                time.sleep(0.1)
            identity=load(started);assert identity['operation_id']==op and identity['pid']==process.pid
            assert process.stdin is not None;process.stdin.write(b'G');process.stdin.flush()
            deadline=time.monotonic()+420
            while not commit.exists():
                if process.poll() is not None:raise RuntimeError('Executor exited before qualified commit; reconcile journal/private diagnostics, never relaunch')
                if time.monotonic()>deadline:raise RuntimeError('Native result wait exceeded: inspect live spawned process and journal, never relaunch')
                time.sleep(0.5)
            committed=load(commit);assert committed['operation_id']==op and committed['executor_pid']==process.pid and process.poll() is None
            status=store.status(op);assert status['state']=='running' and status['phase']=='mutation_started' and status['mutation_started'] and not status['traffic_resumed']
            assert next(e['details']['executor_pid'] for e in status['history'] if e['code']=='reserved')==process.pid
            child=load_docker(config['project']+'-op-'+op+'-native');assert not child['State']['Running'] and child['State']['ExitCode']==0
            phase('terminating_spawned_executor_after_verified_native_commit',executor_pid=process.pid)
            process.kill();exit_code=process.wait(timeout=30)
            if process.stdin:process.stdin.close()
            assert exit_code!=0 and store.status(op)==status
        phase('killed_needs_verification',executor_exit_code=exit_code)
        actual=json.loads(sql(reader,BUSINESS_SQL));before=load(OUTPUT/'business-before.json');schema=json.loads(sql(reader,SCHEMA))
        assert actual['notes']==[{k:v for k,v in n.items() if k!='x_notes_labels'} for n in before['notes']] and actual['boards']==before['boards']
        assert {k:v for k,v in actual.items() if k!='notes'}=={k:v for k,v in before.items() if k!='notes'}
        assert not any(c[1]=='x_notes_labels' for c in schema['columns']) and any(n[0]=='mp_example_notes_labels' and n[1]=='uninstalled' for n in schema['native'])
        assert load(target)==config and all(not native._inspect(reader._container(service,stopped=True))['State']['Running'] for service in ['app','edge'])
        effects=[]
        for line in (store.root/'stages'/op/'native.log').read_text(encoding='utf8').splitlines():
            try:value=json.loads(line)
            except ValueError:continue
            if isinstance(value,dict) and value.get('kind')=='native_uninstall_effects':effects.append(value)
        assert len(effects)==1 and effects[0]['operation_id']==op and effects[0]['plan_hash']==record['plan_hash']
        write('native-effects.json',effects[0]);write('business-after-commit.json',actual);write('schema-after-commit.json',schema);write('journal-after-process-exit.json',status)
        write('process-crash.json',dict(result='actual_executor_OS_termination_after_native_commit',operation_id=op,executor_pid=process.pid,executor_exit_code=exit_code,native_child_id=child['Id'],native_child_exit_code=0,journal_still_running_after_exit=True,python_cleanup_did_not_run=True,traffic_closed=True,labels_field_deleted_before_exit=True,configuration_generation=generation))
        state['phase']='executor_crashed_traffic_closed';(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('crashed_verified_needs_reconciliation');print(json.dumps(dict(result=record['state'],operation_id=op,pid=process.pid,exit_code=exit_code)));return
    if args.action=='reconcile-launcher':
        assert args.run=='01' and record['state']=='awaiting_native_commit' and store.status(op)['state']=='recovery_required'
        child_record=load(LOCAL/(stem+'-child.json'));spawn=load(LOCAL/(stem+'-spawn.json'));assert child_record['pid']!=spawn['executor_pid']
        child=load_docker(config['project']+'-op-'+op+'-native');assert child['State']['ExitCode']==0 and not child['State']['Running']
        write('launcher-reconciliation.json',dict(result='harness_failure_not_OS_crash',operation_id=op,launcher_pid=spawn['executor_pid'],actual_executor_pid=child_record['pid'],native_commit_completed=True,python_cleanup_ran=True,journal_recovery_required=True,correction='Direct sys._base_executable with isolated venv site-packages; PID equality separately verified.'))
        for name,query in [('business-after-commit',BUSINESS_SQL),('schema-after-commit',SCHEMA)]:write(name+'.json',json.loads(sql(reader,query)))
        write('reconciled-status.json',store.status(op));state['phase']='executor_crashed_traffic_closed';(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
        phase('recovery_required_verified');print(json.dumps(dict(result='launcher_attempt_reconciled_requires_restore',operation_id=op)));return
    assert record['state']=='crashed_verified_needs_reconciliation' and store.status(op)['state']=='running'
    before=json.loads(sql(reader,BUSINESS_SQL));old_events=store.status(op)['history']
    r=subprocess.run(prefix+['plugin','apply',op,'--store',str(store.root)]+options,cwd=ROOT,capture_output=True,timeout=120)
    assert r.returncode!=0 and b'recovery_required' in r.stderr
    status=store.status(op);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
    assert status['history'][:-1]==old_events and status['history'][-1]['code']=='executor_lost_after_possible_mutation'
    assert json.loads(sql(reader,BUSINESS_SQL))==before and load(target)==config
    try:UnchangedReleaseRecovery(native).prepare(op)
    except OperatorError as error:write('unchanged-resume-refused.json',dict(result='denied',reason=str(error)))
    else:raise AssertionError('Possibly mutated crash permitted unchanged resume')
    write('reconciled-status.json',status);write('reconciliation.json',dict(result='lost_executor_fenced_before_app_or_stale_state_observation',operation_id=op,no_native_replay=True,traffic_closed=True))
    phase('recovery_required_verified');print(json.dumps(dict(result=record['state'],operation_id=op)))


def load_docker(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]


if __name__=='__main__':main()
