"""Exercise actual supervised lane timing, process loss and effect reconciliation."""
import hashlib
import json
import subprocess
import sys
import time
from types import SimpleNamespace

from background_site import BackgroundSite, ROOT, load, write
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore


SEED = """
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
from uuid import uuid4
assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
result={}
for label, who, workspace, mode, budget, delay in JOBS:
    actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][who]['id'],{}),
                              FIXTURE['workspaces'][workspace]['public_id'])
    run_at=datetime.now(timezone.utc)+timedelta(seconds=delay)
    report=mode=='report'
    handler='report' if report else 'fault'
    inputs=dict(first=1,last=500) if report else dict(mode=mode)
    result[label]=enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:'+handler,
       inputs,str(uuid4()),schedule=JobSchedule(run_at,run_at+timedelta(seconds=90),budget))
    if report:
        env.cr.execute("UPDATE mp_membership m SET state='revoked' FROM mp_principal p WHERE p.id=m.principal_id AND p.public_id=%s AND m.workspace_id=%s",
                       [FIXTURE['users'][who]['principal_id'],FIXTURE['workspaces'][workspace]['id']])
env.cr.commit()
print('BG_SEED='+json.dumps(result))
"""


def docker(*args, data=None):
    return subprocess.run(['docker',*args],input=data,capture_output=True,check=True,timeout=120).stdout


def wait(check, timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=check()
        if result:
            return result
        time.sleep(.2)
    raise AssertionError(f'Observation timeout: {check.__name__}')


class Probe:
    def __init__(self, run, *, extra_phase=None):
        self.site=BackgroundSite(SimpleNamespace(run=run))
        self.state=self.site.state()
        assert self.state['phase'] in {'background_installed','bg02_probed',extra_phase}
        self.project=self.state['project']
        self.target=load(self.site.private/'target.json')
        self.state['database']=self.target['sites'][0]['database']
        self.state['image_id']=self.target['image_id']
        self.fixture=load(self.site.local/'fixtures.json')
        self.operator=JobOperator(OperatorStore(self.site.private/'control'),self.site.private/'target.json')
        self.receipt=self.site.local/'bg03-worker-probe.json'

    def sql(self, text):
        return docker('exec','-i',self.project+'-db-1','psql','-XqAt','-U','postgres',
                      '-v','ON_ERROR_STOP=1','-d',self.state['database'],data=text.encode()).decode().strip()

    def row(self, ident):
        return json.loads(self.sql(f"""SELECT jsonb_build_object('state',state,'progress',progress,'attempts',attempts,
            'generation',claim_generation,'owner',lease_owner,'lease',lease_until,'error',error_code)
            FROM mp_job WHERE public_id='{ident}'"""))

    def seed(self, tag, jobs):
        code='import json\nFIXTURE='+repr(self.fixture)+'\nJOBS='+repr(jobs)+'\n'+SEED
        # Use a copy: the evidence shell phase isn't the site's publication phase.
        raw=self.site.native(dict(self.state),'bg03-'+tag,[],code).decode()
        write(self.site.local/'state.json',self.state)
        item, = [json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BG_SEED=')]
        return item

    def logs(self, name, *, lines='400'):
        result=subprocess.run(['docker','logs','--tail',lines,name],capture_output=True,timeout=15)
        rows=[]
        for line in result.stdout.splitlines():
            if line.startswith(b'{'):
                rows.append(json.loads(line))
        return rows

    def lane(self, ident, generation=1):
        for index in (1,2):
            lane=f'{self.project}-job-bulk-{index}'
            if any(row.get('event')=='claimed' and row.get('job_id')==ident and row.get('generation')==generation
                   for row in self.logs(lane)):
                return lane

    def kill(self, lane):
        before=json.loads(docker('inspect',lane))[0]['RestartCount']
        docker('kill','--signal','KILL',lane)
        def restarted():
            row=json.loads(docker('inspect',lane))[0]
            return row['RestartCount']>before and row['State']['Running']
        try:
            wait(restarted,12)
            return 'automatic'
        except AssertionError:
            row=json.loads(docker('inspect',lane))[0]
            assert not row['State']['Running']
            docker('start',lane)
            return 'operator_start'

    def run(self):
        assert not self.receipt.exists()
        result={'phase':'starting'}
        def checkpoint(phase, **values):
            result.update(phase=phase,**values)
            write(self.receipt,result)
            print(json.dumps(dict(phase=phase)),flush=True)

        self.operator.run('start')
        checkpoint('started',metrics=self.operator.run('metrics'))
        initial=self.seed('initial',[('long','alice','A','heartbeat',20,0),
            ('peer','bob','B','heartbeat',20,0),('waiting','alice','A','retry',15,0)])
        wait(lambda:self.row(initial['long'])['progress']>=25)
        wait(lambda:self.row(initial['peer'])['state']=='running')
        assert self.row(initial['waiting'])['attempts']==0
        first_lease=self.row(initial['long'])['lease']
        wait(lambda:self.row(initial['long'])['lease']!=first_lease and self.row(initial['long'])['state']=='running')
        wait(lambda:self.row(initial['waiting'])['state']=='completed')
        assert self.row(initial['waiting'])['attempts']==2
        assert self.row(initial['peer'])['state']=='completed'
        checkpoint('workspace_limit_and_heartbeat',workspace_limit=True,heartbeat=True,safe_retry_attempts=2)

        timeout=self.seed('timeout',[('timeout','alice','A','timeout',2,0)])['timeout']
        lane=wait(lambda:self.lane(timeout))
        wait(lambda:any(row.get('event')=='watchdog_timeout' for row in self.logs(lane)))
        wait(lambda:self.row(timeout)['state']=='dead_letter')
        assert self.row(timeout)['attempts']==2
        checkpoint('watchdog_timeout',timeout_attempts=2)

        kill=self.seed('kill',[('job','alice','A','claim',18,0)])['job']
        lane=wait(lambda:self.lane(kill))
        old=self.row(kill)
        assert old['state']=='running'
        restart=self.kill(lane)
        wait(lambda:self.row(kill)['state']=='completed')
        assert self.row(kill)['generation']>old['generation']
        code=f"""
from modular_platform import durable
claim=durable.Claim({kill!r},{old['generation']!r},{old['owner']!r})
try:durable.run_fenced(env.cr,claim,lambda row:{{'unexpected':True}})
except durable.ClaimLost: print('BG_STALE_DENIED')
else:raise AssertionError('Old claim reached apply')
"""
        assert b'BG_STALE_DENIED' in self.site.native(dict(self.state),'bg03-stale',[],code)
        write(self.site.local/'state.json',self.state)
        checkpoint('killed_and_reclaimed',restart=restart,stale_claim_denied=True)

        failed=self.seed('operator-retry',[('job','bob','B','report',15,0)])['job']
        wait(lambda:self.row(failed)['state']=='dead_letter')
        assert self.row(failed)['error']=='FORBIDDEN'
        principal=self.fixture['users']['bob']['principal_id']
        workspace=self.fixture['workspaces']['B']['id']
        self.sql(f"""UPDATE mp_membership m SET state='active' FROM mp_principal p
            WHERE p.id=m.principal_id AND p.public_id='{principal}' AND m.workspace_id={workspace};""")
        review=self.operator.run('review',job=failed,action='retry')
        assert self.operator.run('apply',job=failed,action='retry',approval=review['approval'])['applied']
        wait(lambda:self.row(failed)['state']=='completed')
        checkpoint('operator_retry',reviewed_retry=True)

        sink=self.project+'-bg-effect-sink'
        docker('run','-d','--name',sink,'--label','com.modular.disposable='+self.project,
            '--network',self.project+'_runtime','--network-alias','bg-effect-sink',
            '--read-only','--user','10001:10001','--cap-drop','ALL',
            '--mount','type=bind,source='+str(ROOT/'tests/background_effect_sink.py')+',target=/bg-sink.py,readonly',
            '--entrypoint','/venv/bin/python',self.state['image_id'],'/bg-sink.py')
        effect=self.seed('effect',[('job','alice','A','send',20,0)])['job']
        marker=f'accepted:{effect}'.encode()
        wait(lambda:marker in docker('logs',sink))
        lane=wait(lambda:self.lane(effect))
        effect_restart=self.kill(lane)
        wait(lambda:self.row(effect)['state']=='outcome_unknown')
        assert self.row(effect)['attempts']==1
        evidence='sha256:'+hashlib.sha256(marker).hexdigest()
        review=self.operator.run('review',job=effect,action='confirm-delivered',evidence=evidence)
        assert self.operator.run('apply',job=effect,action='confirm-delivered',evidence=evidence,
                                 approval=review['approval'])['applied']
        assert self.row(effect)['state']=='completed' and docker('logs',sink).count(marker)==1
        checkpoint('effect_reconciled',effect_restart=effect_restart,effect_count=1,explicit_reconciliation=True)

        graceful=self.seed('drain',[('job','alice','A','heartbeat',20,0)])['job']
        wait(lambda:self.row(graceful)['state']=='running')
        assert self.operator.run('drain')['lanes']==3
        assert self.row(graceful)['state']=='completed' and self.row(graceful)['attempts']==1
        assert not self.operator._lanes()
        checkpoint('passed',graceful_drain=True)


if __name__=='__main__':
    Probe(sys.argv[1]).run()
