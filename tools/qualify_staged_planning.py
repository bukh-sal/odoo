"""Actual immutable image observation/private stage/plan/approval; never deploy."""
from datetime import datetime,timezone
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_planning import installation_id
from modular_platform.plans import data_digest,plan_hash,_display
from modular_platform.operator_store import OperatorStore
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import OperatorError
from modular import configuration


def invoke(arguments,*,success=True):
    result=subprocess.run(arguments,capture_output=True,timeout=180,cwd=ROOT)
    if (result.returncode==0)!=success:
        raise RuntimeError('Unexpected bounded stage CLI outcome: '+result.stderr.decode(errors='replace')[:800])
    return json.loads(result.stdout if success else result.stderr)


def write(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--image-id');args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 evidence directory required')
    output.mkdir(parents=True)
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());validator=configuration(operator/'trust.json');snapshot=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observation=observer.read();before=observer.state(observation,snapshot)
    old_source=subprocess.check_output(['git','show','00998d2d:packages/platform_sdk/modular_platform/projection.py'],cwd=ROOT)
    old=types.ModuleType('modular_platform.projection_baseline');old.__package__='modular_platform'
    exec(compile(old_source,'qualified_projection_baseline.py','exec'),old.__dict__)
    comparisons=[]
    for name in ('g5','r1'):
        observed_config=json.loads((operator/('targets/'+name+'.json')).read_text());reader=DockerObserver(observed_config);actual=reader.read()
        old_document=old.project_deployment(observed_config,actual,snapshot);new_document=reader.state(actual,snapshot)
        assert old_document==new_document,'Runtime-input extraction must not change qualified state projection'
        comparisons.append({'target':name,'state_digest':data_digest(new_document['state']),'identical_to_qualified_projection':True,
            'workspace_feature_rows':len(new_document['state']['installations']),'bindings':len(new_document['state']['bindings'])})
    write(output/'projection-regression.json',{'result':'passed','baseline_git':'00998d2d','observations':comparisons})
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    candidate=args.image_id or config['image_id']
    descriptor=invoke(prefix+['plugin','stage-image','--image-id',candidate]+options)
    write(output/'staged-image.json',descriptor)
    site=observation['sites'][0];fixture=json.loads((ROOT/'.local/g5/fixtures.json').read_text());workspace=fixture['workspaces']['B']['public_id']
    assert not any(item['workspace_id']==workspace and item['plugin_id']=='org.example.notes' for item in before['state']['installations'])
    nomination={'operation_type':'install','targets':[{'installation_id':installation_id(site,'org.example.notes'),
        'site_id':site['site_id'],'workspace_id':workspace,'plugin_id':'org.example.notes','action':'install'}]}
    write(output/'nomination.json',nomination)
    bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    write(output/'bundle.json',bundle);operation=bundle['plan']['operation_id']
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    forged=copy.deepcopy(bundle);forged['operation_lock']['staged_image']['target_image_id']='sha256:'+'f'*64
    forged['plan']['dependency_lock_digest']=data_digest(forged['operation_lock']);forged['plan_hash']=plan_hash(forged['plan'])
    forged['display']=_display(forged['plan'],forged['operation_lock']);write(output/'forged-image-bundle.json',forged)
    denied=invoke(operations+['register','--bundle',str(output/'forged-image-bundle.json')]+validation,success=False)
    assert 'selected staged release changed' in denied['message'];write(output/'image-substitution-denied.json',denied)
    registered=False
    try:
        result=invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation);registered=True
        write(output/'registered.json',result)
        approved=invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation)
        write(output/'approved.json',approved)
        # Deliberately exercise the wrong adapter directly. The public CLI may
        # support staged execution; a read/plan qualifier must never invoke it.
        try:NativeExecutor(OperatorStore(control),target,catalog_root,validator).apply(operation)
        except OperatorError as error:
            assert 'current-image mutation denied' in str(error)
            write(output/'wrong-executor-denied.json',{'message':str(error)})
        else:raise AssertionError('Current-image adapter accepted a staged plan')
        assert observer.state(observer.read(),snapshot)==before
    finally:
        if registered:write(output/'revoked.json',invoke(operations+['revoke-approval',operation]))
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+[Path(__file__),ROOT/'tools/modular.py']
    write(output/'staged-planning.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':bundle['plan_hash'],'base_image_id':config['image_id'],'target_image_id':candidate,
        'different_image':candidate!=config['image_id'],'stage_digest':descriptor['stage_digest'],
        'observations':['Actual immutable image hashed in network-disabled/read-only/no-live-volume process before private stage enrollment',
            'Current G4/G5 projections byte-equivalent after runtime-input extraction','Actual staged plan includes concrete B workspace/self binding and native backup/restart declaration',
            'Rehashed forged image pin rejected against independent private candidate','Valid stage plan independently registered/exact approved; current-image executor rejected it before reservation/mutation',
            'Whole observed deployment state unchanged, final test approval revoked'],
        'limits':['Candidate was only independently staged/planned/approved; no image was deployed and the final test approval was revoked.',
            'New-image execution/upgrade/uninstall/recovery/startup/client fencing remain pending G5.'],
        'source':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
