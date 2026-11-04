"""One installed manager uninstall, independently approved, then native-commit fault."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-uninstall-recovery-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context as original_context,snapshot,worker,LOCAL,prefix,options,validation
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory,OperatorError
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular_platform.contracts import validate_operations_view
import r1_probe
f.OUTPUT=OUT

def load(path):return json.loads(path.read_bytes())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def save(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def context():return original_context('connector')
def mark(record,phase):record['state']=phase;write(PRIVATE/'state.json',record)

def prepare():
    state,native=context();assert native.config['generation']==6 and not PRIVATE.exists();protect_directory(PRIVATE)
    record=dict(state='observing',configuration=load(native.target_path));write(PRIVATE/'state.json',record)
    before=snapshot(state,'native-uninstall-current-before')
    assert len(before['mp_job'])==1 and before['mp_job'][0]['state']=='completed' and not before['mp_service_credential']
    write(PRIVATE/'data-before.json',before);write(PRIVATE/'worker-before.json',worker(native,'native-uninstall-current-worker-before'))
    files=json.loads(f.command('native-uninstall-current-files-before',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    write(PRIVATE/'files-before.json',files);write(PRIVATE/'dispatch-before.json',ReferenceDispatchMaintenance(native).inspect())
    catalog=Catalog(native.catalog_root,native.validator,readonly=True)
    write(PRIVATE/'published-before.json',native.observer.state(native.observer.read(),catalog.snapshot())['state'])
    fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
    body=dict(schema_version=1,operation='prepare',operation_type='uninstall',plugin_id='org.example.notes_labels',
              site_id=fixture['site_id'],workspace_ids=[],cascade=False)
    status,value=client.request('/api/v1/operations/prepare',body,headers={'X-CSRFToken':client.csrf});assert status==200
    view=validate_operations_view(value['data']);record.update(operation_id=view['operation_id'],plan_hash=view['plan_hash']);mark(record,'prepared')
    status,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',
        operation_id=record['operation_id'],plan_hash=record['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert status==200
    status,value=client.request('/api/v1/operations/bundle/'+record['operation_id']);assert status==200;bundle=value['data']
    assert bundle['plan_hash']==record['plan_hash'] and bundle['plan']['destructive'] and bundle['plan']['backup']['required']
    assert bundle['plan']['operation_type']=='uninstall' and len(bundle['operation_lock']['targets'])==2
    impact=bundle['operation_lock']['native_uninstall_impact']
    assert impact['dispatch']['state']=='present_requires_fence' and impact['native_closure']==['mp_example_notes_labels']
    assert all(t['plugin_id']=='org.example.notes_labels' for t in bundle['operation_lock']['targets'])
    save('bundle.json',bundle);ops=prefix()+['operations','--store',str(native.store.root)]
    save('import.json',json.loads(f.command('native-uninstall-current-import',ops+['import-request',record['operation_id']]+validation(native))))
    review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];save('independent-review.json',review)
    native._runtime_preflight(bundle)
    prior=native.store.status(record['operation_id'])
    negative=subprocess.run(ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+validation(native),capture_output=True,timeout=120)
    write(PRIVATE/'missing-ack.json',dict(exit_code=negative.returncode))
    (PRIVATE/'missing-ack.stdout').write_bytes(negative.stdout);(PRIVATE/'missing-ack.stderr').write_bytes(negative.stderr)
    assert negative.returncode and b'destructive' in negative.stderr.lower() and native.store.status(record['operation_id'])==prior
    f.command('native-uninstall-current-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],
        '--noninteractive','--ack-trust','--ack-destructive']+validation(native))
    mark(record,'approved');f.guard(state)
    save('approved.json',dict(result='installed_manager_native_uninstall_exact_approval',operation_id=record['operation_id'],
        plan_hash=record['plan_hash'],configuration=6,scopes=2,missing_destructive_ack_refused_without_journal_change=True,
        impact_dispatch=impact['dispatch'],native_closure=impact['native_closure'],mutation_started=False))
    print(json.dumps(dict(result='native_uninstall_reviewed_approved',operation_id=record['operation_id'],scopes=2)),flush=True)

class InjectedNativeCommitFault(OperatorError):pass

def fault():
    state,native=context();record=load(PRIVATE/'state.json')
    assert record['state']=='approved' and load(native.target_path)==record['configuration']
    fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL
    client=r1_probe.Client(state,fixture,'operator')
    write(PRIVATE/'old-session.json',dict(session_id=next(c.value for c in client.jar if c.name=='session_id'),
        release_token=client.release_token))
    operation=record['operation_id'];original=native._private_command
    def private(args,path,**kwargs):
        result=original(args,path,**kwargs)
        if Path(path).name=='native.log':
            effects=[]
            for line in Path(path).read_text(encoding='utf8').splitlines():
                try:value=json.loads(line)
                except ValueError:continue
                if isinstance(value,dict) and value.get('kind')=='native_uninstall_effects':effects.append(value)
            assert len(effects)==1 and effects[0]['operation_id']==operation
            write(PRIVATE/'native-commit-marker.json',dict(state='native_committed_then_controlled_exception',operation_id=operation))
            save('native-effects.json',effects[0])
            raise InjectedNativeCommitFault('Owned rehearsal fault after real native commit, before metadata or traffic')
        return result
    mark(record,'applying_native_commit_fault')
    with patch.object(native,'_private_command',side_effect=private):
        try:native.apply(operation)
        except InjectedNativeCommitFault:pass
        else:raise AssertionError('Expected genuine native-commit boundary not reached')
    status=native.store.status(operation)
    assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
    assert load(PRIVATE/'native-commit-marker.json')['state']=='native_committed_then_controlled_exception'
    query="BEGIN READ ONLY;SELECT jsonb_build_object('labels_state',(SELECT state FROM ir_module_module WHERE name='mp_example_notes_labels'),'labels_column',EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='mp_example_note' AND column_name='x_notes_labels'),'notes',(SELECT count(*) FROM mp_example_note),'boards',(SELECT count(*) FROM mp_example_canvas_board));ROLLBACK;"
    observed=json.loads(f.sql(state,'native-uninstall-current-native-effect',query))
    assert observed==dict(labels_state='uninstalled',labels_column=False,notes=2,boards=1)
    checkpoint=load(native.store.root/'checkpoints'/operation/'manifest.json')
    dispatch=ReferenceDispatchMaintenance(native).inspect();assert dispatch==checkpoint['dispatch_profile'] and dispatch['control']['state']=='paused'
    assert worker(native,'native-uninstall-current-failed-worker')==load(PRIVATE/'worker-before.json')
    assert not native._inspect(record['configuration']['worker_id'])['State']['Running']
    assert not native._inspect(state['project']+'-edge-1')['State']['Running']
    assert load(native.target_path)==record['configuration'];f.guard(state)
    record['status']=status;mark(record,'recovery_required_native_committed')
    save('fault.json',dict(result='passed_actual_native_uninstall_commit_fault_closed',operation_id=operation,status=status,
        native_effect=observed,checkpoint_dispatch_exact_after_native_uninstall=True,dispatch=dispatch,
        worker_identity_image_key_publication_exact=True,configuration_unchanged=True,
        limits=['Actual native commit and controlled failure, not restored/resumed yet. Current native data missing Labels column; preserve failed DB and authority.']))
    print(json.dumps(dict(result='native_uninstall_committed_fault_verified',operation_id=operation,traffic_closed=True)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','fault']);args=parser.parse_args();globals()[args.action]()
