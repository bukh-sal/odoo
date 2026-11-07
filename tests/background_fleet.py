"""Qualify reviewed profiles against one owned native Docker site."""
import argparse
from datetime import datetime, timezone
import json
import subprocess
import time
from unittest.mock import patch
from uuid import uuid4

from background_site import load, write
from background_workers import Probe, docker, wait
from modular_platform.job_fleet import JobFleet
from modular_platform.operator_os import OperatorError


class FleetProbe(Probe):
    def __init__(self):
        super().__init__('bx-02-worker-profile-01',extra_phase='bg03-fleet-forced')
        if self.state['phase']=='bg03-fleet-forced':
            self.state['phase']='bg02_probed'
        self.receipt=self.site.local/'bx02-fleet.json'
        self.result=load(self.receipt) if self.receipt.exists() else {'checks':{}}

    def record(self, name, **value):
        self.result['checks'][name]=value
        self.result['utc']=datetime.now(timezone.utc).isoformat()
        write(self.receipt,self.result)
        print(json.dumps(dict(check=name,**value)),flush=True)

    def ready(self):
        state=self.operator.run('status')
        return state if state['state']=='ready' else None

    def profile(self, **options):
        review=self.operator.run('profile-review',**options)
        state=self.operator.run('profile-apply',approval=review['approval'])
        assert state['state']=='ready',state
        return state

    def initial(self):
        assert 'initial' not in self.result['checks']
        assert self.operator.run('status')['state']=='unconfigured'
        state=self.profile(urgent_lanes=1,bulk_lanes=1)
        assert all(value['desired']==value['ready']==1 for value in state['pools'].values())
        self.record('initial',status=state)

    def pins(self):
        runtime=self.operator.runtime()
        pins=JobFleet(self.operator)._pins(runtime)
        result={}
        for key,value in (('SITE_ID',str(uuid4())),('RELEASE_DIGEST','sha256:'+'0'*64),
                          ('INVENTORY_DIGEST','sha256:'+'0'*64),('DATABASE','nonexistent_disposable_database')):
            base=self.operator._base(runtime,self.project+'-wrong-'+key.lower())
            prefix='MP_EXPECTED_'+key+'='
            base=[prefix+value if item.startswith(prefix) else item for item in base]
            extra=[]
            for pin in ('SITE_ID','RELEASE_DIGEST'):
                if not any(item.startswith('MP_EXPECTED_'+pin+'=') for item in base):
                    extra.extend(['--env','MP_EXPECTED_'+pin+'='+(value if key==pin else pins[pin.lower()])])
            process=subprocess.run(['docker','run','--rm',*extra,*base,'-m','modular_platform.job_runner',
                '--pool','bulk','--poll-seconds','.25'],capture_output=True,timeout=40)
            assert process.returncode!=0,(key,process.stdout)
            result[key]={'exit_code':process.returncode,'refused':True}
        self.record('wrong_pins',results=result)

    def resize(self):
        before=self.operator.run('status')
        state=self.profile(urgent_lanes=1,bulk_lanes=2)
        retained={row['name']:row['container'] for row in before['lanes']}
        assert all(retained.get(row['name'],row['container'])==row['container'] for row in state['lanes'])
        lane=self.project+'-job-bulk-2'
        drained=self.operator.run('drain-lane',pool='bulk',lane=2)
        assert drained['pools']['bulk']==dict(desired=2,running=1,ready=1,drained=1),drained
        assert lane not in self.operator._lanes()
        assert self.operator.run('reconcile')['pools']['bulk']['drained']==1
        state=self.profile(urgent_lanes=1,bulk_lanes=2)
        self.record('resize_and_selected_drain',retained_containers=retained,status=state)

    def partial(self):
        review=self.operator.run('profile-review',urgent_lanes=1,bulk_lanes=3)
        original=self.operator.docker
        expected=self.project+'-job-bulk-3'
        def fail(*args,**kwargs):
            if args[0]=='run' and expected in args:raise OperatorError('Injected partial start')
            return original(*args,**kwargs)
        with patch.object(self.operator,'docker',side_effect=fail):
            try:self.operator.run('profile-apply',approval=review['approval'])
            except OperatorError as error:assert 'Injected' in str(error)
            else:raise AssertionError('Partial start was not injected')
        partial=self.operator.run('status')
        assert partial['state']=='partial' and partial['pools']['bulk']['desired']==3
        assert partial['pools']['bulk']['ready']==2,partial
        recovered=self.operator.run('profile-apply',approval=review['approval'])
        assert recovered['state']=='ready' and recovered['generation']==partial['generation']
        self.record('partial_start',partial=partial,recovered=recovered)

    def connection(self):
        lane=self.project+'-job-bulk-3'
        network=self.project+'_runtime'
        docker('network','disconnect',network,lane)
        try:
            unavailable=self.operator.run('status')
            assert not next(row for row in unavailable['lanes'] if row['name']==lane)['ready']
            started=time.monotonic()
            def unhealthy():
                row=json.loads(docker('inspect',lane))[0]
                return row if row['State']['Health']['Status']!='healthy' else None
            disconnected=wait(unhealthy,25)
            detection=time.monotonic()-started
        finally:
            docker('network','connect',network,lane)
        restored=wait(self.ready,90)
        self.record('connection_loss',unavailable=unavailable,docker_health=disconnected['State']['Health']['Status'],
                    docker_detection_seconds=detection,recovered=restored)

    def active(self):
        # This reference handler computes for nine seconds and makes no remote write.
        ident=self.seed('fleet-active',[('job','alice','A','heartbeat',20,0)])['job']
        wait(lambda:self.row(ident)['state']=='running')
        lane=wait(lambda:next((name for name in self.operator._lanes()
            if any(row.get('event')=='claimed' and row.get('job_id')==ident for row in self.logs(name))),None))
        number=int(lane.rsplit('-',1)[1])
        before=self.row(ident)
        started=time.monotonic()
        state=self.operator.run('drain-lane',pool='bulk',lane=number)
        elapsed=time.monotonic()-started
        after=self.row(ident)
        assert after['state']=='completed' and after['attempts']==before['attempts']==1,(before,after)
        assert lane not in self.operator._lanes()
        assert state['pools']['urgent']['ready']==1
        self.record('active_graceful_drain',job=ident,before=before,after=after,seconds=elapsed,status=state)

    def resources(self):
        names=list(self.operator._lanes())
        stats=json.loads(b'['+b','.join(docker('stats','--no-stream','--format','{{json .}}',*names).splitlines())+b']')
        rows=json.loads(self.sql("SELECT COALESCE(jsonb_agg(row_to_json(a)),'[]') FROM (SELECT application_name,state,wait_event_type,count(*) AS connections FROM pg_stat_activity WHERE datname=current_database() GROUP BY 1,2,3) a"))
        limits={name:dict(memory=row['HostConfig']['Memory'],nano_cpus=row['HostConfig']['NanoCpus'],pids=row['HostConfig']['PidsLimit']) for name,row in self.operator._lanes().items()}
        self.record('resource_snapshot',limits=limits,stats=stats,database_connections=rows)

    def forced(self):
        assert 'forced_drain' not in self.result['checks']
        state=self.profile(urgent_lanes=1,bulk_lanes=2,shutdown_seconds=5)
        ident=self.seed('fleet-forced-'+uuid4().hex[:8],[('job','alice','A','heartbeat',20,0)])['job']
        wait(lambda:self.row(ident)['state']=='running')
        old=self.row(ident)
        lane=wait(lambda:next((name for name in self.operator._lanes()
            if any(row.get('event')=='claimed' and row.get('job_id')==ident for row in self.logs(name))),None))
        number=int(lane.rsplit('-',1)[1])
        # Freeze only the active child to model a stuck computation. The short
        # reference handler otherwise finishes during the operator's preflight.
        docker('exec',lane,'/venv/bin/python','-c',
               "import json,os,signal; p=json.load(open('/tmp/mp-job-health.json')); os.kill(p['pid'],signal.SIGSTOP)")
        started=time.monotonic()
        drained=self.operator.run('drain-lane',pool='bulk',lane=number)
        elapsed=time.monotonic()-started
        after=wait(lambda:self.row(ident) if self.row(ident)['state']=='completed' else None,45)
        assert after['attempts']==2 and after['generation']>old['generation'],(old,after,elapsed)
        code=f"""
from modular_platform import durable
claim=durable.Claim({ident!r},{old['generation']!r},{old['owner']!r})
try:durable.run_fenced(env.cr,claim,lambda row:{{'unexpected':True}})
except durable.ClaimLost: print('BX02_STALE_DENIED')
else:raise AssertionError('Interrupted claim reached apply')
"""
        assert b'BX02_STALE_DENIED' in self.site.native(dict(self.state),'bx02-stale-forced',[],code)
        write(self.site.local/'state.json',self.state)
        self.record('forced_drain',job=ident,old_claim=old,after=after,seconds=elapsed,
                    frozen_compute_child=True,stale_claim_denied=True,status=drained)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actions',nargs='+',choices=['initial','pins','resize','partial','connection','active','resources','forced'])
    args=parser.parse_args()
    probe=FleetProbe()
    for action in args.actions:getattr(probe,action)()
