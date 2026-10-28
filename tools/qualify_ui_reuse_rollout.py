"""Once-only independently approved platform UI/guard image rollout on G5."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.workers import snapshots
from modular import configuration
from qualify_staged_planning import invoke,write
from qualify_release_reader_rollout import notes_snapshot,files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--image-id',required=True);parser.add_argument('--apply',action='store_true',required=True)
    parser.add_argument('--expected-generation',type=int,default=12,help='Exact independent base generation; each output has its own once-only marker')
    args=parser.parse_args();output=args.output.resolve();local=ROOT/'.local/g5'
    markers=local/'platform-rollouts';markers.mkdir(exist_ok=True)
    marker=local/'ui-reuse-rollout.json' if args.expected_generation==12 else markers/(output.name+'.json')
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():
        raise ValueError('Fresh once-only UI rollout required; reconcile prior marker/journal, never repeat')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());local_state=json.loads((local/'state.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and local_state['disposable'] and config['published_release']
    assert config['sites'][0]['database']==local_state['active_db'] and config['generation']==args.expected_generation
    validator=configuration(operator/'trust.json');snapshot=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observed=observer.read();before=observer.state(observed,snapshot)['state']
    notes=notes_snapshot(observer);old_files=files(observer);assert len(notes)==4
    output.mkdir(parents=True);write(output/'state-before.json',before)
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    descriptor=invoke(prefix+['plugin','stage-image','--image-id',args.image_id]+options);write(output/'staged-image.json',descriptor)
    from modular_platform.release_staging import StageStore
    _,staged=StageStore(OperatorStore(control),config,Catalog(catalog_root,validator,readonly=True)).load(descriptor)
    old=observed['runtime']['inventory']['files'];new=staged['runtime']['inventory']['files']
    changed={name for name in old.keys()|new.keys() if old.get(name)!=new.get(name)}
    assert observed['runtime']['inventory']['artifacts']==staged['runtime']['inventory']['artifacts']
    rows=before['installations'];assert len(rows)==3
    nomination={'operation_type':'deploy','targets':[{name:row[name] for name in ('installation_id','site_id','workspace_id','plugin_id')}|{'action':'deploy'} for row in rows]}
    write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle)
    write(marker,{'operation_id':operation,'state':'nominated','plan_hash':bundle['plan_hash'],'evidence':str(output.relative_to(ROOT))})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    denied=invoke(prefix+['plugin','apply',operation]+options,success=False)
    assert 'without reconciliation' in denied['message']
    write(output/'unapproved-denied.json',denied)
    denied=invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive']+validation,success=False)
    assert 'acknowledgment' in denied['message']
    write(output/'missing-trust-ack-denied.json',denied)
    assert observer.state(observer.read(),snapshot)['state']==before
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation}),flush=True)
    native=StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator);completed=native.apply(operation)
    write(output/'completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed']
    assert (control/'stages'/operation/'native-skipped.json').is_file() and not (control/'stages'/operation/'native.log').exists()
    current=json.loads(target.read_text());reader=DockerObserver(current);after=reader.state(reader.read(),snapshot)['state']
    assert current['image_id']==args.image_id and after['installations']==before['installations'] and after['bindings']==before['bindings']
    assert notes_snapshot(reader)==notes
    current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in old_files.items())
    write(output/'state-after.json',after);assert native.apply(operation)==completed
    local_state.update(image_id=current['image_id'],worker_id=current['worker_id'],release_generation=current['generation'],stage='ui_reuse_rollout_completed')
    local_state['evidence_history']=list(dict.fromkeys(local_state.get('evidence_history',[])+[local_state['evidence']]))
    local_state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(local_state,indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id':operation,'state':'completed','plan_hash':bundle['plan_hash'],'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    paths=[path for path in (ROOT/'platform_addons/mp_shell').rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    paths+=[Path(__file__),ROOT/'packages/platform_sdk/modular_platform/worker_start.py',ROOT/'tools/start_worker.py',ROOT/'deploy/Dockerfile']
    write(output/'ui-rollout.json',{'result':'passed_rollout_browser_pending','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':bundle['plan_hash'],'generation':current['generation'],'image_id':current['image_id'],
        'worker_id':current['worker_id'],'database':current['sites'][0]['database'],'changed_inventory_paths':sorted(changed),
        'existing_business_rows_files_feature_scopes_bindings_preserved':True,'completed_replay_no_mutation':True,
        'unapproved_and_missing_native_trust_ack_denied':True,'native_orm_maintenance_skipped':True,
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limits':['Actual native dialogs/focus/Escape/command/notification/CRUD behavior remains browser qualification.',
            'No WebClient replacement, action/router pilot, client epoch/UI07 or G5 exit claimed.']})
    print(json.dumps({'result':'passed_rollout_browser_pending','generation':current['generation'],'operation_id':operation}),flush=True)


if __name__=='__main__':main()
