"""Once-only staged worker replacement and pre-traffic recovery rehearsal.

Only the named disposable G5 target is allowed. Durable nomination precedes
approval/mutation; an interrupted attempt must be reconciled, never repeated.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,_run
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.workers import snapshots
from modular import configuration
from qualify_staged_planning import invoke,write


def business_snapshot(observer):
    database=observer._container('db');name=observer.config['sites'][0]['database']
    sql="""BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT jsonb_build_object(
 'notes',COALESCE((SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'[]'::jsonb),
 'attachments',COALESCE((SELECT jsonb_agg(to_jsonb(a) ORDER BY id) FROM ir_attachment a WHERE res_model='mp.example.note'),'[]'::jsonb));
ROLLBACK;"""
    raw=_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d',name,'-v','ON_ERROR_STOP=1'],input=sql.encode())
    value=json.loads(raw)
    code="""import hashlib,json,pathlib,sys
root=pathlib.Path('/var/lib/modular/filestore')/sys.argv[1]
print(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}))"""
    files=json.loads(_run(['docker','exec',observer._container('app'),'/venv/bin/python','-c',code,name]))
    return {'notes_count':len(value['notes']),'attachment_count':len(value['attachments']),
        'business_rows_digest':data_digest(value),'filestore_files':len(files),'filestore_digest':data_digest(files)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--image-id',required=True);parser.add_argument('--apply',action='store_true',required=True)
    parser.add_argument('--fault-before-traffic',action='store_true');args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 evidence directory required')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    marker=ROOT/'.local/g5'/('staged-fault-execution.json' if args.fault_before_traffic else 'staged-promotion-execution.json')
    if marker.exists():raise OperatorError('Execution already nominated; reconcile marker/journal/children without repeating')
    config=json.loads(target.read_text());local=json.loads((ROOT/'.local/g5/state.json').read_text())
    if (config['project']!='mp-r0-r1g5fd0445d406d6' or local['profile']!='G5' or not local['disposable']
            or config['sites'][0]['database']!=local['active_db']):raise OperatorError('Exact current disposable G5 target required')
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True);snapshot=catalog.snapshot()
    observer=DockerObserver(config);observed=observer.read();before=observer.state(observed,snapshot)['state']
    business=business_snapshot(observer);old_workers=snapshots(config)
    fixture=json.loads((ROOT/'.local/g5/fixtures.json').read_text());workspace=fixture['workspaces']['B']['public_id']
    if any(item['workspace_id']==workspace and item['plugin_id']=='org.example.notes' for item in before['installations']):
        raise OperatorError('This qualification requires Notes installed only in workspace A')
    output.mkdir(parents=True)
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    descriptor=invoke(prefix+['plugin','stage-image','--image-id',args.image_id]+options)
    write(output/'staged-image.json',descriptor)
    # This bounded first replacement changes host/SDK bytes, not native core
    # addons. Core-update planning is qualified separately before such images.
    from modular_platform.release_staging import StageStore
    _,staged=StageStore(OperatorStore(control),config,catalog).load(descriptor)
    packaged={item['addon'] for item in observed['runtime']['inventory']['artifacts'].values()}
    def core_files(runtime):
        return {name:value for name,value in runtime['inventory']['files'].items()
            if name.startswith(('addons/','odoo/')) and not any(name.startswith('addons/'+addon+'/') for addon in packaged)}
    assert core_files(observed['runtime'])==core_files(staged['runtime']),'This run does not authorize changed core/native bytes'
    installation=next(item['installation_id'] for item in before['installations'] if item['plugin_id']=='org.example.notes')
    nomination={'operation_type':'install','targets':[{'installation_id':installation,'site_id':fixture['site_id'],
        'workspace_id':workspace,'plugin_id':'org.example.notes','action':'install'}]}
    write(output/'nomination.json',nomination)
    bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle);write(output/'state-before.json',before)
    write(marker,{'operation_id':operation,'plan_hash':bundle['plan_hash'],'evidence':str(output.relative_to(ROOT)),
        'state':'nominated','fault_before_traffic':args.fault_before_traffic})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    apply=prefix+['plugin','apply',operation]+options
    denied=invoke(apply,success=False);assert 'without reconciliation' in denied['message']
    assert observer.state(observer.read(),snapshot)['state']==before
    write(output/'unapproved-denied.json',{'result':denied,'unchanged':True})
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],
        '--noninteractive','--ack-trust','--ack-permissions']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation,'fault_before_traffic':args.fault_before_traffic}),flush=True)
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator)
    if args.fault_before_traffic:
        advance=store.advance
        def fault(selected,locks,phase,**kwargs):
            result=advance(selected,locks,phase,**kwargs)
            if selected==operation and phase=='release_published':raise OperatorError('Disposable qualification fault after publication before traffic')
            return result
        with patch.object(store,'advance',side_effect=fault):
            try:native.apply(operation)
            except OperatorError as error:
                if 'Disposable qualification fault' not in str(error):raise
            else:raise AssertionError('Expected bounded fault did not occur')
        failed=store.status(operation);write(output/'failed-status.json',failed)
        assert failed['state']=='recovery_required' and failed['mutation_started'] and not failed['traffic_resumed']
        changed=json.loads(target.read_text());assert changed['image_id']==args.image_id and changed['worker_id']
        changed_observer=DockerObserver(changed)
        assert not json.loads(_run(['docker','inspect',changed_observer._container('edge',stopped=True)]))[0]['State']['Running']
        assert business_snapshot(changed_observer)==business
        write(output/'failed-workers.json',snapshots(changed))
        print(json.dumps({'stage':'recovery_required','operation_id':operation,'new_image_published':True,'traffic_closed':True}),flush=True)
        # Fresh local executor observes the published candidate configuration.
        recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
        decision=recovery.prepare(operation);digest=data_digest(decision)
        write(output/'restore-decision.json',decision)
        write(output/'restore-result.json',recovery.execute(decision,exact_hash=digest,noninteractive=True))
        restored_config=json.loads(target.read_text());assert restored_config['image_id']==config['image_id']
        assert restored_config['generation']>changed['generation'] and restored_config['sites'][0]['database']!=config['sites'][0]['database']
        restored_observer=DockerObserver(restored_config)
        after=restored_observer.state(restored_observer.read(),snapshot)['state']
        assert after['installations']==before['installations'] and after['bindings']==before['bindings']
        assert business_snapshot(restored_observer)==business
        recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
        resume=recovery.prepare_resume(operation);write(output/'resume-decision.json',resume)
        write(output/'resume-result.json',recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True))
        assert store.status(operation)['state']=='revoked'
        outcome='restored_previous_image_fresh_database'
    else:
        completed=native.apply(operation);write(output/'completed.json',completed)
        assert completed['state']=='completed' and completed['traffic_resumed']
        restored_config=json.loads(target.read_text());assert restored_config['image_id']==args.image_id
        restored_observer=DockerObserver(restored_config);after=restored_observer.state(restored_observer.read(),snapshot)['state']
        assert after['release_digest']==bundle['plan']['target_release_digest'] and len(after['installations'])==len(before['installations'])+1
        assert business_snapshot(restored_observer)==business
        replay=native.apply(operation);assert replay==completed
        write(output/'completed-replay.json',{'unchanged_status':True})
        outcome='completed'
    assert set(item['container_id'] for item in old_workers)<=set(item['container_id'] for item in snapshots(restored_config))
    # A normal public health probe after the separately journaled traffic fence.
    import urllib.request
    assert urllib.request.urlopen('http://127.0.0.1:18072/web/login',timeout=10).status==200
    write(output/'state-after.json',after)
    local['active_db']=restored_config['sites'][0]['database'];local['image_id']=restored_config['image_id'];local['worker_id']=restored_config['worker_id']
    local['release_generation']=restored_config['generation'];local['stage']=outcome
    local['databases']=list(dict.fromkeys(local['databases']+[local['active_db']]))
    local['evidence_history']=list(dict.fromkeys(local.get('evidence_history',[])+[local['evidence']]))
    local['evidence']=str(output.relative_to(ROOT));(ROOT/'.local/g5/state.json').write_text(json.dumps(local,indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id':operation,'plan_hash':bundle['plan_hash'],'evidence':str(output.relative_to(ROOT)),'state':outcome},indent=2)+'\n')
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+[Path(__file__),ROOT/'tools/modular.py']
    write(output/'staged-execution.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':bundle['plan_hash'],'outcome':outcome,'base_image':config['image_id'],
        'candidate_image':args.image_id,'final_configuration':restored_config,'business_preserved':business,
        'old_workers_retained':True,'startup_guard_used':True,'checks':['Exact independent approval before maintenance',
            'Real checkpoint/native metadata mutation and guarded worker replacement',
            'Exact release/binding/feature/permission readiness before publication',
            'Post-publication/pre-traffic fault enters recovery_required and restores old code into a fresh DB with a new epoch'
            if args.fault_before_traffic else 'Completed same-operation replay does not repeat native mutation',
            'Business rows and filestore byte hashes preserved; public health restored'],
        'limitations':['This is a same-native-artifact image replacement, not a plugin version/schema upgrade or uninstall.',
            'Client release fencing, startup default profile and the broader fault matrix remain G5 work.'],
        'source':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'outcome':outcome,'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
