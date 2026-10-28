"""Consume a real browser request through independent CLI authority/apply."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.app_channel import read_request,journal_view,MIRROR_WRITER
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,_run
from modular_platform.plans import check_bundle
from modular_platform.operator_store import OperatorStore
from modular import configuration


def invoke(command,*,success=True):
    result=subprocess.run(command,capture_output=True,timeout=240,cwd=ROOT)
    if (result.returncode==0)!=success:
        raise RuntimeError('Unexpected bounded CLI outcome: '+result.stderr.decode(errors='replace')[:700])
    return json.loads(result.stdout if success else result.stderr)


def write(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation_id');parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--download',required=True,type=Path);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 evidence directory required')
    output.mkdir(parents=True)
    target=ROOT/'.local/operator/targets/g5.json';config=json.loads(target.read_text())
    validator=configuration(ROOT/'.local/operator/trust.json');catalog_root=ROOT/'.local/operator/catalog'
    observer=DockerObserver(config);snapshot=Catalog(catalog_root,validator,readonly=True).snapshot()
    before=observer.state(observer.read(),snapshot)['state'];request=read_request(observer,args.operation_id)
    bundle=json.loads(args.download.read_text());assert bundle==request['bundle'];check_bundle(bundle,before)
    assert bundle['plan']['operation_type']=='suspend' and len(bundle['operation_lock']['targets'])==1
    write(output/'browser-downloaded-bundle.json',bundle);write(output/'state-before.json',before)
    app=observer._container('app');started=json.loads(_run(['docker','inspect','--format','{{json .State.StartedAt}}',app]))
    prefix=[sys.executable,'tools/modular.py','--config','.local/operator/trust.json']
    control=ROOT/'.local/operator/control';operations=prefix+['operations','--store',str(control)]
    options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    initial=invoke(operations+['import-request',args.operation_id]+options)
    assert initial['state']=='awaiting_operator_approval';write(output/'independent-registration.json',initial)
    # App/native code can fabricate app-DB progress. It cannot write/consume an
    # OS approval. Exercise that boundary with a typed but fabricated mirror.
    fake_status={**initial,'state':'approved','approval_expires_at':(datetime.now(timezone.utc)+timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ')}
    fake=journal_view(bundle,fake_status,request,before)
    _run(['docker','exec','-i',app,'/venv/bin/python','-c',MIRROR_WRITER],input=json.dumps({'site_id':request['site_id'],'view':fake}).encode())
    apply=prefix+['plugin','apply',args.operation_id,'--store',str(control)]+options
    try:
        denied=invoke(apply,success=False)
        assert denied['error']=='VALIDATION_FAILED' and 'without reconciliation' in denied['message']
        assert observer.state(observer.read(),snapshot)['state']==before
        write(output/'forged-app-approval-denied.json',{'result':'passed','app_mirror_state':'approved',
            'independent_store_state':OperatorStore(control).status(args.operation_id)['state'],'base_state_unchanged':True,'cli_denial':denied})
    finally:
        restored=invoke(operations+['mirror-status',args.operation_id]+options)
        write(output/'awaiting-real-approval-mirror.json',restored)
    approved=invoke(operations+['approve',args.operation_id,'--plan-hash',bundle['plan_hash'],'--noninteractive']+options)
    assert approved['state']=='approved';write(output/'approved.json',approved)
    mirror=invoke(operations+['mirror-status',args.operation_id]+options);assert mirror['state']=='approved'
    write(output/'approved-mirror.json',mirror)
    print(json.dumps({'stage':'approved','operation_id':args.operation_id,'plan_hash':bundle['plan_hash']}),flush=True)
    completed=invoke(apply);assert completed['state']=='completed'
    assert not any(event['code'] in ('migrated','workers_replaced') for event in completed['history'])
    write(output/'completed.json',completed)
    mirror=invoke(operations+['mirror-status',args.operation_id]+options);assert mirror['state']=='completed'
    assert mirror['dimensions'][0]['database_state']=='installed' and mirror['dimensions'][0]['feature_state']=='suspended'
    write(output/'completed-mirror.json',mirror)
    after=observer.state(observer.read(),snapshot)['state'];write(output/'state-after.json',after)
    assert before['release_lock']==after['release_lock'] and before['bindings']==after['bindings']
    assert json.loads(_run(['docker','inspect','--format','{{json .State.StartedAt}}',app]))==started
    assert invoke(apply)==completed
    files=[ROOT/'tools/modular.py',Path(__file__)]+[ROOT/'packages/platform_sdk/modular_platform'/name for name in
        ['app_channel.py','feature_executor.py','feature_metadata.py','operator_store.py','approval_validation.py']]
    write(output/'app-operation.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':args.operation_id,'plan_hash':bundle['plan_hash'],'checks':['Browser-prepared/submitted/downloaded exact plan equals app request',
        'Independent CLI reconstructs/imports, fabricated app approval cannot apply or change base state',
        'Exact local approval and typed redacted awaiting/approved/completed status mirrors',
        'Actual atomic feature suspension, DB installation retained, release/bindings unchanged',
        'No native migration/worker restart claimed or performed, completed replay stable'],
        'limits':['Browser final progress observation, data retention/API gates and re-enable are recorded separately.','General native new-image lifecycle and full G5 exit remain pending.'],
        'source':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in files}})
    print(json.dumps({'result':'passed_subset','evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
