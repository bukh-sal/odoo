"""Once-only owned46→47 fixture; preserve every uncertain attempt and checkpoint."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'release')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image,DockerObserver
from modular_platform.foundation_transition import declare_transition,observe_effects,_psql
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore,_write_new
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore,prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor
from initialize_reference import configuration,write,load
from qualify_release_reader_rollout import files

WORK=ROOT/'.local/addon-cleanup/baseline46'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','apply','fault','capture','restore','resume'])
    p.add_argument('--candidate',type=Path)
    p.add_argument('--label',required=True)
    p.add_argument('--site',choices=['maintenance','aurora','fault'],default='maintenance')
    p.add_argument('--populated',action='store_true',help='Require actual existing native plugin installations')
    a=p.parse_args();assert a.label.replace('-','').isalnum()
    work=WORK if a.site=='maintenance' else ROOT/'.local/addon-cleanup'/('aurora46' if a.site=='aurora' else 'fault46')
    private=work/'private';operator=private/'reference/operator'
    native=StagedNativeExecutor(OperatorStore(operator/'control'),operator/'target.json',private/'catalog',configuration(operator/'trust.json'))
    path=operator/(a.label+'.json')
    if a.phase=='prepare':
        assert not path.exists(),'Never overwrite/replay an existing attempt'
        runtime=inspect_image(native.config['image_id']);candidate=load(a.candidate)
        after=inspect_image(candidate['image_id'])
        declaration=declare_transition(native.config,candidate['image_id'],runtime,after)
        _write_new(operator/(a.label+'-declaration.json'),declaration)
        catalog=Catalog(native.catalog_root,native.validator,readonly=True)
        stages=StageStore(native.store,native.config,catalog)
        descriptor=stages.stage(candidate['image_id'],foundation_transition=declaration)
        _,staged=stages.load(descriptor)
        observation=native.observer.read();snapshot=catalog.snapshot()
        document=native.observer.state(observation,snapshot)
        targets=[{key:r[key] for key in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='deploy')
                 for r in document['state']['installations']]
        assert bool(targets)==a.populated,'Declare actual plugin-free or populated qualification scope'
        bundle=prepare_staged_plan(document,observation['sites'],snapshot,after,descriptor,targets=targets,
            operation_type='core_upgrade',operation_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            base_runtime=runtime,foundation_transition=staged['foundation_transition'])
        assert bundle['plan']['site_ids'] and bool(bundle['plan']['artifacts'])==a.populated and bundle['plan']['backup']['required']
        record=dict(phase='registering',operation=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],
            base=native.config,candidate=candidate['image_id'],files=files(native.observer),effects=declaration['site_effects'])
        write(path,record)
        validate=native._validate();native.store.register(bundle,validate)
        review=native.store.review(record['operation'],validate)
        approval=native.store.approve(record['operation'],exact_hash=bundle['plan_hash'],noninteractive=True,
            revalidate=validate,acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=False))
        record.update(phase='approved',review_digest=data_digest(review),approval_digest=data_digest(approval))
    else:
        record=load(path);operation=record['operation']
        if a.phase in ('apply','fault'):
            assert record['phase']=='approved'
            record['phase']='applying';write(path,record)
            if a.phase=='fault':
                advance=native.store.advance
                def inject(op,locks,phase,**details):
                    result=advance(op,locks,phase,**details)
                    if op==operation and phase=='release_published':raise OperatorError('AR controlled publication failure')
                    return result
                with patch.object(native.store,'advance',side_effect=inject):
                    try:native.apply(operation)
                    except OperatorError as error:assert 'AR controlled publication failure' in str(error)
                    else:raise AssertionError('Fault was not reached')
            else:
                result=native.apply(operation);assert result['state']=='completed' and result['traffic_resumed']
                target=load(native.target_path);assert target['image_id']==record['candidate']
                current_files=files(DockerObserver(target))
                assert all(current_files.get(k)==v for k,v in record['files'].items())
                record['phase']='verified'
        elif a.phase=='restore':
            assert record['phase']=='recovery_required'
            recovery=RestoreExecutor(native);decision=recovery.prepare(operation)
            record.update(phase='restoring',restore_digest=data_digest(decision));write(path,record)
            recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
            target=load(native.target_path)
            assert target['image_id']==record['base']['image_id'] and target['sites'][0]['database']!=record['base']['sites'][0]['database']
            assert observe_effects(target)==record['effects'],'Original IAP/application/ownership data must return'
            assert files(DockerObserver(target))==record['files']
            record.update(phase='restored_closed',restored_database=target['sites'][0]['database'])
        elif a.phase=='resume':
            assert record['phase']=='restored_closed'
            recovery=RestoreExecutor(native);decision=recovery.prepare_resume(operation)
            recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
            assert native.store.status(operation)['state']=='revoked'
            record.update(phase='verified_restored',separate_resume=True,resume_digest=data_digest(decision))
        if a.phase in ('fault','capture'):
            status=native.store.status(operation)
            assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
            target=load(native.target_path)
            subprocess.run(['docker','stop',target['worker_id']],check=True,capture_output=True,timeout=45)
            record.update(phase='recovery_required',failed_app_stopped=True,failure_phase=status['phase'])
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],operation=record['operation'],label=a.label)),flush=True)


if __name__=='__main__':main()
