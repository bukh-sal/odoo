"""Once-only approved47→49 forward/fault and independent fresh recovery."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_release_site import ReleaseSite,load,write
from modular_platform import tasks_adoption as ta
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image,DockerObserver
from modular_platform.foundation_transition import declare_transition
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore,_write_new
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore,prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor
from initialize_reference import configuration
from qualify_release_reader_rollout import files


def make_executor(site):
    return StagedNativeExecutor(OperatorStore(site.private/'control'),site.private/'target.json',
                               site.private/'catalog',configuration(site.private/'trust.json'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','apply','fault','capture','restore','resume'])
    p.add_argument('--run',required=True)
    p.add_argument('--site',choices=['tasks','maintenance'],required=True)
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--label',required=True)
    p.add_argument('--candidate',type=Path)
    args=p.parse_args()
    assert args.label.replace('-','').isalnum()
    site=ReleaseSite(args);native=make_executor(site)
    path=site.local/(args.label+'.json')
    if args.phase=='prepare':
        assert not path.exists(),'Inspect existing attempt; never overwrite/replay it'
        candidate=load(args.candidate)
        assert candidate['state']=='built'
        before=inspect_image(native.config['image_id']);after=inspect_image(candidate['image_id'])
        assert after['inventory_digest']==candidate['inventory_digest']
        declaration=declare_transition(native.config,candidate['image_id'],before,after,recipe=ta.RECIPE)
        _write_new(site.private/(args.label+'-declaration.json'),declaration)
        catalog=Catalog(native.catalog_root,native.validator,readonly=True)
        stages=StageStore(native.store,native.config,catalog)
        descriptor=stages.stage(candidate['image_id'],foundation_transition=declaration)
        _,record=stages.load(descriptor)
        observed=native.observer.read();snapshot=catalog.snapshot();document=native.observer.state(observed,snapshot)
        targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='deploy')
                 for r in document['state']['installations']]
        adoption=ta.adoption_target(declaration)
        if adoption:targets.append(adoption)
        bundle=prepare_staged_plan(document,observed['sites'],snapshot,after,descriptor,targets=targets,
            operation_type='core_upgrade',operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            base_runtime=before,foundation_transition=record['foundation_transition'])
        assert bundle['plan']['backup']['required'] and bundle['plan']['destructive']
        result=dict(phase='registering',operation=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],
            base=native.config,candidate=candidate['image_id'],files=files(native.observer),effects=declaration['site_effects'],
            adoption=adoption,scope='populated sealed47 native app adoption' if adoption else 'Maintenance with Tasks remaining absent')
        write(path,result)
        validate=native._validate();native.store.register(bundle,validate)
        review=native.store.review(result['operation'],validate)
        approval=native.store.approve(result['operation'],exact_hash=bundle['plan_hash'],noninteractive=True,
            revalidate=validate,acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=False))
        result.update(phase='approved',review_digest=data_digest(review),approval_digest=data_digest(approval))
    else:
        result=load(path);operation=result['operation']
        if args.phase in {'apply','fault'}:
            assert result['phase']=='approved'
            result['phase']='applying';write(path,result)
            if args.phase=='fault':
                advance=native.store.advance
                def inject(op,locks,phase,**details):
                    value=advance(op,locks,phase,**details)
                    if op==operation and phase=='release_published':raise OperatorError('AT controlled publication failure')
                    return value
                with patch.object(native.store,'advance',side_effect=inject):
                    try:native.apply(operation)
                    except OperatorError as error:
                        if 'AT controlled publication failure' not in str(error):raise
                    else:raise AssertionError('Requested controlled failure not reached')
            else:
                applied=native.apply(operation)
                assert applied['state']=='completed' and applied['traffic_resumed']
                target=load(native.target_path);assert target['image_id']==result['candidate']
                current=files(DockerObserver(target));assert all(current.get(k)==v for k,v in result['files'].items())
                observation=StagedNativeExecutor(native.store,native.target_path,native.catalog_root,native.validator).observer.read()
                installed={r['plugin_id']:r for r in observation['sites'][0]['installations']}
                assert (ta.APP in installed)==bool(result['adoption'])
                if result['adoption']:
                    assert installed[ta.APP]['version']==ta.VERSION
                result.update(phase='verified',preserved_original_files=True,package_adoption_verified=bool(result['adoption']))
        elif args.phase=='restore':
            assert result['phase']=='recovery_required'
            recovery=RestoreExecutor(native);decision=recovery.prepare(operation)
            result.update(phase='restoring',restore_digest=data_digest(decision));write(path,result)
            recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
            target=load(native.target_path)
            assert target['image_id']==ta.SOURCE_IMAGE and target['sites'][0]['database']!=result['base']['sites'][0]['database']
            assert ta.observe_effects(target)==result['effects']
            assert files(DockerObserver(target))==result['files']
            receipt=load(native.store.root/'recoveries'/operation/'result.json')
            assert receipt['keep_traffic_closed']
            result.update(phase='restored_closed',fresh_database=target['sites'][0]['database'],exact_old_application_and_files=True)
        elif args.phase=='resume':
            assert result['phase']=='restored_closed'
            recovery=RestoreExecutor(native);decision=recovery.prepare_resume(operation)
            recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
            assert native.store.status(operation)['state']=='revoked'
            result.update(phase='verified_restored',separate_resume=True,resume_digest=data_digest(decision))
        if args.phase in {'fault','capture'}:
            status=native.store.status(operation)
            assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
            failed=load(native.target_path)
            subprocess.run(['docker','stop',failed['worker_id']],check=True,capture_output=True,timeout=45)
            raw=subprocess.run([sys.executable,'-I',str(ROOT/'tools/modular.py'),'--config',str(site.private/'trust.json'),
                'operations','--store',str(native.store.root),'show',operation],check=True,capture_output=True,timeout=40).stdout
            assert json.loads(raw)['state']=='recovery_required'
            result.update(phase='recovery_required',failed_app_stopped=True,independent_cli_journal=True,failure_phase=status['phase'])
    write(path,result)
    print(json.dumps(dict(phase=result['phase'],operation=result['operation'],site=args.site,label=args.label)),flush=True)


if __name__=='__main__':main()
