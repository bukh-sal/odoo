"""Once-only current-image Canvas installation for UI05/UI10 requalification."""
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
from modular_platform.lifecycle_planning import installation_id
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from qualify_native_upgrade import sql
from qualify_staged_planning import invoke,write
from qualify_release_reader_rollout import notes_snapshot,files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--apply',action='store_true',required=True);args=parser.parse_args()
    output=args.output.resolve();local=ROOT/'.local/g5';marker=local/'canvas-reuse-install.json'
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():
        raise ValueError('Fresh once-only Canvas regression install required; inspect any existing journal, never repeat')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());state=json.loads((local/'state.json').read_text());fixture=json.loads((local/'fixtures.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==15 and state['disposable']
    assert config['sites'][0]['database']==state['active_db'] and config['published_release']
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observed=observer.read();before=observer.state(observed,catalog)['state']
    assert not any(row['plugin_id']=='org.example.canvas' for row in before['installations'])
    assert json.loads(sql(observer,"SELECT to_jsonb(to_regclass('mp_example_canvas_board') IS NOT NULL);")) is False
    notes=notes_snapshot(observer);old_files=files(observer);assert len(notes)==4 and len(before['installations'])==3
    output.mkdir(parents=True);write(output/'state-before.json',before)
    write(output/'preservation-before.json',{'notes':notes,'filestore':old_files})
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',config['image_id']]+options))
    nomination={'operation_type':'install','targets':[{'installation_id':installation_id(observed['sites'][0],'org.example.canvas'),
        'site_id':fixture['site_id'],'workspace_id':fixture['workspaces']['A']['public_id'],'plugin_id':'org.example.canvas','action':'install'}]}
    write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle)
    write(marker,{'operation_id':operation,'plan_hash':bundle['plan_hash'],'state':'nominated','evidence':str(output.relative_to(ROOT))})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    denied=invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation,success=False)
    assert 'acknowledgment' in denied['message'];write(output/'missing-permission-ack-denied.json',denied)
    assert observer.state(observer.read(),catalog)['state']==before
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation}),flush=True)
    executor=StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator);completed=executor.apply(operation)
    write(output/'completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed']
    current=json.loads(target.read_text());reader=DockerObserver(current);after=reader.state(reader.read(),catalog)['state']
    assert current['image_id']==config['image_id'] and current['generation']==16
    assert notes_snapshot(reader)==notes and all(files(reader).get(name)==digest for name,digest in old_files.items())
    by_scope=lambda rows:{(row['installation_id'],row['workspace_id']):row for row in rows}
    previous=by_scope(before['installations']);actual=by_scope(after['installations'])
    assert len(actual)==4 and all(actual.get(key)==row for key,row in previous.items())
    canvas=[row for row in after['installations'] if row['plugin_id']=='org.example.canvas']
    assert len(canvas)==1 and canvas[0]['workspace_id']==fixture['workspaces']['A']['public_id'] and canvas[0]['feature_state']=='enabled'
    new_bindings={row['binding_id']:row for row in after['bindings']}
    assert all(new_bindings.get(row['binding_id'])==row for row in before['bindings'])
    assert json.loads(sql(reader,"SELECT to_jsonb(to_regclass('mp_example_canvas_board') IS NOT NULL);")) is True
    write(output/'state-after.json',after);assert executor.apply(operation)==completed
    state.update(image_id=current['image_id'],worker_id=current['worker_id'],release_generation=current['generation'],stage='canvas_reuse_installed')
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id':operation,'plan_hash':bundle['plan_hash'],'state':'completed','generation':current['generation'],'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    report={'result':'passed_install_browser_pending','utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,
        'plan_hash':bundle['plan_hash'],'image_id':current['image_id'],'generation':current['generation'],'worker_id':current['worker_id'],
        'database':current['sites'][0]['database'],'permission_changes':bundle['plan']['permission_changes'],
        'original_notes_and_prior_assets_scopes_bindings_preserved':True,'same_operation_replay_inert':True,
        'state_digest':data_digest(after),'source_sha256':{Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'limits':['Canvas repeated mount/dispose and expired-session draft recovery still need actual browser qualification.']}
    write(output/'canvas-install.json',report);print(json.dumps({'result':report['result'],'generation':current['generation'],'operation_id':operation}),flush=True)


if __name__=='__main__':main()
