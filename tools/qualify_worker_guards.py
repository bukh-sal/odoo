"""Actual pre-import denial probes with read-only DB access and isolated roots."""
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
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration

PROBE="""import json,pathlib,sys
data=json.load(sys.stdin)
namespace={'__name__':'qualified_guard'}
exec(compile(data['source'],'qualified_guard.py','exec'),namespace)
if data['case']=='extra_addon':
 pathlib.Path('/opt/modular/addons/mp_guard_unexpected/__init__.py').write_text("raise RuntimeError('must never import')")
sys.argv=['guard',data['database'],data['inventory']]
try:namespace['main']()
except ValueError as error:
 assert data['message'] in str(error),'Wrong failure boundary'
 assert not any(name=='odoo' or name.startswith('odoo.') for name in sys.modules),'Native import occurred before denial'
 print(json.dumps({'case':data['case'],'result':'denied_before_native_import','native_imported':False}))
else:raise AssertionError('Guard unexpectedly returned')
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--previous-image-id',required=True);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 evidence directory required')
    operator=ROOT/'.local/operator';target=json.loads((operator/'targets/g5.json').read_text())
    if target['project']!='mp-r0-r1g5fd0445d406d6' or target['image_id']==args.previous_image_id:raise ValueError('Exact promoted disposable G5 target required')
    store=OperatorStore(operator/'control');store._authorize_plan({'deployment_id':target['deployment_id'],
        'site_ids':[item['site_id'] for item in target['sites']],'policy_version':target['policy_version'],
        'operator_authorization_generation':target['operator_authorization_generation']})
    validator=configuration(operator/'trust.json');catalog=Catalog(operator/'catalog',validator,readonly=True).snapshot()
    observer=DockerObserver(target);observed=observer.read();before=observer.state(observed,catalog)['state']
    previous=inspect_image(args.previous_image_id)
    if previous['inventory_digest']==observed['runtime']['inventory_digest']:raise ValueError('Different retained inventory required for DB-pin denial')
    output.mkdir(parents=True);source_path=ROOT/'packages/platform_sdk/modular_platform/worker_start.py';source=source_path.read_text()
    cases=[('wrong_inventory_pin',target['image_id'],'sha256:'+'0'*64,'inventory pin mismatch'),
        ('wrong_database_inventory',args.previous_image_id,previous['inventory_digest'],'Database release inventory differs'),
        ('extra_addon',target['image_id'],observed['runtime']['inventory_digest'],'search-path content')]
    results=[]
    for case,image,pin,message in cases:
        command=['docker','run','--rm','-i','--read-only','--user','10001:10001','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--network',target['project']+'_runtime','--pids-limit','128',
            '--memory','512m','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777',
            '--mount','type=volume,source='+target['project']+'_appconfig,target=/run/secrets,readonly']
        if case=='extra_addon':command+=['--tmpfs','/opt/modular/addons/mp_guard_unexpected:rw,nosuid,nodev,noexec,size=1m,mode=1777']
        # No filestore, host path, Docker socket, approvals or writable DB is
        # mounted/provided. The fixed guard opens a READ ONLY connection.
        command+=['--entrypoint','/venv/bin/python',image,'-c',PROBE]
        result=subprocess.run(command,input=json.dumps({'case':case,'source':source,'database':target['sites'][0]['database'],
            'inventory':pin,'message':message}).encode(),capture_output=True,timeout=90)
        if result.returncode:raise RuntimeError('Pre-import guard probe failed: '+case)
        results.append(json.loads(result.stdout))
    assert observer.state(observer.read(),catalog)['state']==before
    report={'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),'image_id':target['image_id'],
        'previous_image_id':args.previous_image_id,'observations':results,'deployment_state_unchanged':True,
        'state_digest':data_digest(before),'source_sha256':{source_path.relative_to(ROOT).as_posix():hashlib.sha256(source_path.read_bytes()).hexdigest(),
            Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'limits':['Actual negative probes qualify executor-created worker guards; fresh-install default startup and complete G5 acceptance remain pending.']}
    (output/'worker-guards.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'passed_subset','cases':len(results),'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
