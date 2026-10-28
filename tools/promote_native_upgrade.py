"""Once-only successful native version upgrade after populated recovery proof."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.workers import snapshots
from modular import configuration
from qualify_native_upgrade import sql,SCHEMA_SQL
from qualify_staged_execution import business_snapshot
from qualify_staged_planning import invoke,write


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--image-id',required=True);parser.add_argument('--apply',action='store_true',required=True);args=parser.parse_args()
    output=args.output.resolve();local=ROOT/'.local/g5';marker=local/'native023-promotion.json'
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():
        raise ValueError('Fresh once-only promotion required; reconcile existing marker, never repeat')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());state=json.loads((local/'state.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and state['disposable'] and state['active_db']==config['sites'][0]['database']
    assert json.loads((local/'native023-fault.json').read_text())['state']=='restored_verified_and_resumed'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);before=observer.state(observer.read(),catalog)['state'];business=business_snapshot(observer)
    assert business['notes_count']==4 and json.loads(sql(observer,SCHEMA_SQL))['native_version']=='19.0.0.2.2'
    old_workers=snapshots(config);rows=[row for row in before['installations'] if row['plugin_id']=='org.example.notes']
    assert len(rows)==2 and {row['feature_state'] for row in rows}=={'enabled','suspended'}
    output.mkdir(parents=True);write(output/'state-before.json',before)
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',args.image_id]+options))
    nomination={'operation_type':'upgrade','targets':[{name:row[name] for name in ('installation_id','site_id','workspace_id','plugin_id')}|{'action':'upgrade'} for row in rows]}
    write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle)
    write(marker,{'operation_id':operation,'state':'nominated','plan_hash':bundle['plan_hash'],'evidence':str(output.relative_to(ROOT))})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation}),flush=True)
    native=StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator)
    completed=native.apply(operation);assert completed['state']=='completed' and completed['traffic_resumed'];write(output/'completed.json',completed)
    current=json.loads(target.read_text());reader=DockerObserver(current);observed=reader.read();after=reader.state(observed,catalog)['state']
    assert current['image_id']==args.image_id and after['release_digest']==bundle['plan']['target_release_digest']
    assert after['installations']==before['installations'] and after['bindings']==before['bindings']
    assert business_snapshot(reader)==business
    schema=json.loads(sql(reader,SCHEMA_SQL));assert schema['native_version']=='19.0.0.2.3' and schema['metadata_version']=='0.2.3'
    assert schema['positive_constraint'] is True and schema['migration_pre']==schema['migration_post']
    assert json.loads(schema['migration_pre'])['from_native_version']=='19.0.0.2.2'
    write(output/'schema-after.json',schema);write(output/'state-after.json',after)
    assert {row['container_id'] for row in old_workers}<={row['container_id'] for row in snapshots(current)}
    replay=native.apply(operation);assert replay==completed;write(output/'completed-replay.json',{'unchanged_status':True})
    refreshed=subprocess.run([sys.executable,'tools/publish_profile.py','--target',str(target)],capture_output=True,timeout=90,cwd=ROOT)
    assert refreshed.returncode==0;write(output/'profile-refresh.json',json.loads(refreshed.stdout))
    state.update(active_db=current['sites'][0]['database'],image_id=current['image_id'],worker_id=current['worker_id'],
        release_generation=current['generation'],stage='native023_upgrade_completed')
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id':operation,'state':'completed','evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+list((ROOT/'platform_addons/mp_example_notes').rglob('*.py'))+[Path(__file__),ROOT/'plugins/notes/plugin.toml']
    paths=[path for path in paths if '__pycache__' not in path.parts]
    write(output/'native-upgrade.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':bundle['plan_hash'],'from_version':'0.2.2','to_version':'0.2.3',
        'configuration':current,'business_preserved':business,'suspended_scope_preserved':True,
        'actual_migrations_and_constraint':True,'old_workers_retained':True,'completed_replay_no_new_mutation':True,
        'limitations':['Skipped-release/fresh-install migration qualification, uninstall/removal, default startup/client fencing and full G5 exit remain pending.',
            'Sanitized profile refreshed manually; automatic publication remains pending.'],
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'outcome':'native023_upgrade_completed','evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
