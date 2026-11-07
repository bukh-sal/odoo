"""Race reviewed resizing with actual core maintenance on the owned BX-02 site."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

from background_fleet import FleetProbe
from background_site import Catalog, configuration, load, ROOT, write
from modular_platform.deployment import DockerObserver
from modular_platform.job_operator import JobOperator
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import LockBusy, OperatorError
from modular_platform.release_staging import StageStore, prepare_staged_plan


RESIZE = """
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from modular_platform.job_operator import JobOperator
from modular_platform.job_fleet import JobFleet
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import LockBusy
from unittest.mock import patch
store,target,approval,ready=sys.argv[2:]
op=JobOperator(OperatorStore(store),target)
if approval=='review':
    try:op.run('profile-review',urgent_lanes=1,bulk_lanes=1)
    except LockBusy:print('BX02_RESIZE_BUSY')
    else:raise AssertionError('Resize entered while upgrade owns locks')
else:
    reconcile=JobFleet.reconcile
    def held(self):
        Path(ready).write_text('locked',encoding='utf8')
        assert sys.stdin.buffer.read(1)==b'R'
        return reconcile(self)
    with patch.object(JobFleet,'reconcile',held):
        result=op.run('profile-apply',approval=approval)
    assert result['state']=='ready',result
    print('BX02_RESIZE_READY')
"""


def run(candidate):
    probe=FleetProbe()
    path=probe.site.local/'bx02-fleet-release.json'
    assert not path.exists(),'Inspect recorded lifecycle before retrying'
    record=dict(phase='preparing',checks={})
    def save(phase,**values):
        record.update(phase=phase,**values)
        write(path,record)
        print(json.dumps(dict(phase=phase)),flush=True)
    target=probe.site.private/'target.json'
    catalog_path=probe.site.private/'catalog'
    validator=configuration(probe.site.private/'trust.json')
    catalog=Catalog(catalog_path,validator,readonly=True)
    store=probe.operator.store
    observer=DockerObserver(probe.target)
    observed=observer.read()
    before=observer.state(observed,catalog.snapshot())
    stages=StageStore(store,probe.target,catalog)
    descriptor=stages.stage(load(candidate)['image_id'])
    _,staged=stages.load(descriptor)
    targets=[{key:row[key] for key in ('installation_id','site_id','workspace_id','plugin_id')}
             | {'action':'deploy'} for row in before['state']['installations']]
    operation=str(uuid4())
    bundle=prepare_staged_plan(before,observed['sites'],catalog.snapshot(),staged['runtime'],descriptor,
        targets=targets,operation_type='core_upgrade',operation_id=operation,
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=observed['runtime'])
    executor=StagedNativeExecutor(store,target,catalog_path,validator)
    validate=executor._validate()
    store.register(bundle,validate)
    store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
        acknowledgments={'destructive':True,'trust_expansion':True,'permission_expansion':False})
    save('approved',operation=operation,old_pins=JobFleetPins(probe))
    try:executor.apply(operation)
    except OperatorError as error:assert 'Pause and drain' in str(error),str(error)
    else:raise AssertionError('Active fleet entered native maintenance')
    assert store.status(operation)['state']=='approved' and not store.status(operation)['mutation_started']
    record['checks']['active_fleet_refused_before_reserve']=True
    assert probe.operator.run('drain')['state']=='paused'
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
    marker=probe.site.local/'resize-lock-ready.txt'
    args=[sys.executable,'-c',RESIZE,str(ROOT/'packages/platform_sdk'),str(store.root),str(target),review['approval'],str(marker)]
    child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+45
        while not marker.exists():
            assert child.poll() is None,'Resize exited before lock checkpoint'
            assert time.monotonic()<deadline,'Resize lock checkpoint timeout'
            time.sleep(.1)
        try:executor.apply(operation)
        except LockBusy:pass
        else:raise AssertionError('Upgrade entered during locked resize')
        output,error=child.communicate(input=b'R',timeout=120)
        assert child.returncode==0,error.decode()
        assert b'BX02_RESIZE_READY' in output,output
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=15)
    assert store.status(operation)['state']=='approved' and not store.status(operation)['mutation_started']
    record['checks']['upgrade_refused_while_resize_locked']=True
    assert probe.operator.run('drain')['state']=='paused'
    stale=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=1)
    original=executor._runtime_preflight
    def preflight(value):
        original(value)
        result=subprocess.run([sys.executable,'-c',RESIZE,str(ROOT/'packages/platform_sdk'),str(store.root),str(target),'review','unused'],
                              capture_output=True,timeout=20)
        assert result.returncode==0,result.stderr.decode()
        assert b'BX02_RESIZE_BUSY' in result.stdout,result.stdout
        record['checks']['resize_refused_while_upgrade_locked']=True
        save('applying')
    with patch.object(executor,'_runtime_preflight',side_effect=preflight):
        result=executor.apply(operation)
    assert result['state']=='completed' and result['traffic_resumed'],result
    probe.operator=JobOperator(store,target)
    try:probe.operator.run('reconcile')
    except OperatorError as error:assert 'different deployment release' in str(error),str(error)
    else:raise AssertionError('Old profile accepted on new release')
    try:probe.operator.run('profile-apply',approval=stale['approval'])
    except OperatorError as error:assert 'pins' in str(error),str(error)
    else:raise AssertionError('Old review accepted on new release')
    record['checks']['old_profile_and_review_refused']=True
    current=probe.profile(urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
    assert current['pins']['image_id']==load(candidate)['image_id']
    assert current['pins']['release_digest']!=record['old_pins']['release_digest']
    record['checks']['new_release_ready']=True
    save('passed',status=current,operation_status=store.status(operation))


def JobFleetPins(probe):
    return probe.operator.run('status')['pins']


if __name__=='__main__':run(Path(sys.argv[1]))
