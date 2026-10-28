"""Finish only local bookkeeping after the recorded completed deploy; no apply."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import notes_snapshot,files


def main():
    local=ROOT/'.local/g5';operator=ROOT/'.local/operator';control=operator/'control';marker=local/'ui-reuse-rollout.json'
    previous=json.loads(marker.read_text());operation=previous['operation_id']
    assert operation=='0835fda3-1aea-4aec-8470-f73bc6f139f1' and previous['state']=='nominated'
    output=ROOT/previous['evidence'];assert (output/'postcheck-failure.json').is_file() and not (output/'ui-rollout.json').exists()
    store=OperatorStore(control);completed=store.status(operation);assert completed==json.loads((output/'completed.json').read_text())
    assert completed['state']=='completed' and completed['traffic_resumed']
    target=json.loads((operator/'targets/g5.json').read_text());assert target['generation']==13 and target['image_id']=='sha256:cbcde2443fd7d5b4667550e1a2e53efda9faa365857fb1e777b93bd4f6689af2'
    observer=DockerObserver(target);catalog=Catalog(operator/'catalog',configuration(operator/'trust.json'),readonly=True).snapshot()
    after=observer.state(observer.read(),catalog)['state'];before=json.loads((output/'state-before.json').read_text())
    assert after==json.loads((output/'state-after.json').read_text())
    assert after['installations']==before['installations'] and after['bindings']==before['bindings']
    notes=notes_snapshot(observer);assert len(notes)==4
    migration=json.loads(sql(observer,"SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.post';"))
    assert hashlib.sha256(json.dumps(notes,sort_keys=True,separators=(',',':')).encode()).hexdigest()==migration['rows_sha256']
    checkpoint=control/'checkpoints'/completed['backup_id'];saved={}
    with tarfile.open(checkpoint/'filestore.tar.gz') as archive:
        for member in archive:
            if member.isfile():
                prefix='filestore/'+target['sites'][0]['database']+'/'
                assert member.name.startswith(prefix)
                saved[member.name.removeprefix(prefix)]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    actual=files(observer);assert len(saved)==40 and all(actual.get(name)==digest for name,digest in saved.items())
    assert (control/'stages'/operation/'native-skipped.json').is_file() and not (control/'stages'/operation/'native.log').exists()
    state=json.loads((local/'state.json').read_text());state.update(image_id=target['image_id'],worker_id=target['worker_id'],
        release_generation=target['generation'],stage='ui_reuse_rollout_completed')
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    marker.write_text(json.dumps(previous|{'state':'completed'},indent=2)+'\n')
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))
    paths+=[path for path in (ROOT/'platform_addons/mp_shell').rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    paths+=[Path(__file__),ROOT/'tools/qualify_ui_reuse_rollout.py',ROOT/'tools/modular.py']
    report={'result':'passed_rollout_browser_pending','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':previous['plan_hash'],'generation':target['generation'],'image_id':target['image_id'],
        'worker_id':target['worker_id'],'database':target['sites'][0]['database'],'state_digest':data_digest(after),
        'unapproved_and_missing_trust_ack_denied':True,'native_orm_maintenance_skipped':True,
        'preserved':{'full_original_notes_rows_excluding_later_added_labels_column':4,'original_asset_files':len(saved),'installations_and_bindings':True},
        'postcheck_reconciliation':'Completed journal/read-only business/checkpoint verification; update local status only, never repeat apply.',
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limits':['New UI browser qualification, action/view pilot, client release fence and complete G5 remain pending.']}
    (output/'ui-rollout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'generation':target['generation'],'operation_id':operation,'no_apply_invoked':True}))


if __name__=='__main__':main()
