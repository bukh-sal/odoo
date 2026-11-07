"""Independent reviewed worker profiles and resumable Docker reconciliation."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from .operator_os import OperatorError, protect_directory
from .operator_store import _write_new
from .plans import data_digest
from .worker_operator import private_json


POOLS = ('urgent', 'bulk', 'producer')
HEALTH_COMMAND = '/venv/bin/python -m modular_platform.job_health'


class JobFleet:
    def __init__(self, operator):
        self.operator = operator
        self.directory = protect_directory(operator.records / 'fleets' / operator.deployment / operator.site['site_id'])
        self.path = self.directory / 'desired.json'

    def desired(self):
        return private_json(self.path) if self.path.exists() else None

    def _save(self, value):
        temporary = self.directory / (uuid4().hex+'.tmp')
        _write_new(temporary, value)
        os.replace(temporary, self.path)

    def _pins(self, runtime):
        op = self.operator
        return dict(deployment_id=op.deployment, site_id=op.site['site_id'], database=op.site['database'],
                    image_id=op.target['image_id'], inventory_digest=runtime['inventory_digest'],
                    release_digest=data_digest(op.target['published_release']),
                    target_digest=data_digest(op.target))

    @staticmethod
    def _spec(urgent_lanes, bulk_lanes, cpu_millis, memory_mib, shutdown_seconds, producer_lanes=0):
        counts = dict(urgent=urgent_lanes, bulk=bulk_lanes, producer=producer_lanes)
        if (any(type(value) is not int or not 0 <= value <= 8 for value in counts.values())
                or producer_lanes not in (0,1) or not 1 <= sum(counts.values()) <= 8
                or type(cpu_millis) is not int or not 250 <= cpu_millis <= 2000
                or type(memory_mib) is not int or not 256 <= memory_mib <= 2048
                or type(shutdown_seconds) is not int or not 5 <= shutdown_seconds <= 3605):
            raise OperatorError('Worker profile exceeds the supported lane or resource ranges')
        return dict(counts=counts, cpu_millis=cpu_millis, memory_mib=memory_mib, shutdown_seconds=shutdown_seconds)

    @staticmethod
    def _observation(lanes):
        return {name:dict(id=row['Id'],image=row['Image'],config=data_digest(row['Config']),
                          host=data_digest(row['HostConfig']),running=row['State']['Running'])
                for name,row in lanes.items()}

    def review(self, *, urgent_lanes=1, bulk_lanes=2, producer_lanes=0, cpu_millis=1000, memory_mib=768, shutdown_seconds=45, paused=False):
        op = self.operator
        if type(paused) is not bool:raise OperatorError('Explicit reviewed fleet pause state required')
        spec = self._spec(urgent_lanes, bulk_lanes, cpu_millis, memory_mib, shutdown_seconds, producer_lanes)
        runtime = op.runtime()
        lanes = op._lanes()
        if any(not row['Config']['Labels'].get('com.modular.job_template') for row in lanes.values()):
            raise OperatorError('Drain legacy lanes before adopting a reviewed worker profile')
        capacity = json.loads(op.docker('info','--format','{{json .}}'))
        total = sum(spec['counts'].values())
        if total*memory_mib*1024**2 > capacity['MemTotal'] or total*cpu_millis > capacity['NCPU']*1000:
            raise OperatorError('Requested worker limits exceed the Docker host capacity')
        pins = self._pins(runtime)
        previous = self.desired()
        recurrence=None
        if producer_lanes or (previous or {}).get('recurrence_policy') is not None:
            files=runtime['inventory']['files']
            for filename in ('recurrence_runner.py','recurrence_authority.py'):
                path=Path(__file__).with_name(filename)
                if files.get('packages/platform_sdk/modular_platform/'+filename)!=hashlib.sha256(path.read_bytes()).hexdigest():
                    raise OperatorError('Recurring producer requires its exact reviewed runtime')
            observed=op._run_admin(runtime,str(uuid4()),['recurrence-authority'])
            if observed.get('event')!='recurrence_authority' or observed.get('policy',{}).get('site_id')!=op.site['site_id']:
                raise OperatorError('Exact native recurrence authority review required')
            recurrence=observed['policy']
        value = dict(protocol=1, review_id=str(uuid4()), pins=pins, spec=spec,
                     state='paused' if paused else 'active',
                     recurrence_policy=recurrence,
                     previous_digest=data_digest(previous), observed=self._observation(lanes),
                     reviewed_at=datetime.now(timezone.utc).isoformat())
        approval = data_digest(value)
        _write_new(self.directory/(approval[7:]+'.review.json'),value)
        return dict(event='job_profile_review',approval=approval,**value)

    def apply(self, approval):
        if not isinstance(approval,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',approval):
            raise OperatorError('Exact worker profile review digest required')
        value = private_json(self.directory/(approval[7:]+'.review.json'))
        op = self.operator
        runtime = op.runtime()
        if data_digest(value)!=approval or value['pins']!=self._pins(runtime):
            raise OperatorError('Worker profile review differs from current deployment pins')
        self._check_authority(runtime,value.get('recurrence_policy'))
        desired = self.desired()
        intent = self.directory/(approval[7:]+'.intent.json')
        if intent.exists():
            if not desired or desired['approval']!=approval:
                if data_digest(desired)!=value['previous_digest']:
                    raise OperatorError('Worker profile attempt requires reconciliation of its current desired state')
                self._save(private_json(intent)['target'])
            return self.reconcile()
        expiry=datetime.fromisoformat(value['reviewed_at'])+timedelta(seconds=op.store.policy['maximum_start_lifetime'])
        if datetime.now(timezone.utc)>=expiry or data_digest(desired)!=value['previous_digest']:
            raise OperatorError('Worker profile review expired or its desired state changed')
        if value['observed']!=self._observation(op._lanes()):
            raise OperatorError('Worker containers changed after profile review')
        template=data_digest(dict(pins=value['pins'],resources={key:item for key,item in value['spec'].items() if key!='counts'}))
        accepted = sorted(set((desired or {}).get('accepted_templates',[])+([desired['template']] if desired else [])))
        target=dict(protocol=1,approval=approval,pins=value['pins'],spec=value['spec'],template=template,
                    recurrence_policy=value.get('recurrence_policy'),
                    accepted_templates=accepted,state=value.get('state','active'),drained_lanes=[],
                    generation=(desired['generation']+1 if desired else 1))
        _write_new(intent,dict(approval=approval,target=target))
        self._save(target)
        result=self.reconcile()
        _write_new(self.directory/(approval[7:]+'.result.json'),result)
        return result

    def _expected(self, desired):
        op=self.operator
        if desired['state']=='paused':
            return set()
        return {f'{op.project}-job-{pool}-{number}' for pool,count in desired['spec']['counts'].items()
                for number in range(1,count+1)}-set(desired['drained_lanes'])

    def _check_authority(self,runtime,policy):
        if policy is None:return
        current=self.operator._run_admin(runtime,str(uuid4()),['recurrence-authority'])
        if current.get('event')!='recurrence_authority':raise OperatorError('Current recurrence authority observation required')
        observed=current.get('policy',{})
        if any(observed.get(key)!=policy.get(key) for key in ('protocol','kind','site_id')):
            raise OperatorError('Recurring role authority differs from its review')
        expected={binding['credential_id']:binding for binding in policy['credentials']}
        if any(expected.get(binding['credential_id'])!=binding for binding in observed['credentials']):
            raise OperatorError('Recurring role authority changed; review the current credential scope')

    def _matches(self, row, desired):
        op=self.operator
        pool=row['Config']['Labels']['com.modular.job_pool']
        pins=desired['pins']; spec=desired['spec']; config=row['Config']; host=row['HostConfig']
        env=set(config['Env'])
        expected_env={'MP_EXPECTED_DATABASE='+pins['database'],'MP_EXPECTED_INVENTORY_DIGEST='+pins['inventory_digest'],
                      'MP_EXPECTED_SITE_ID='+pins['site_id'],'MP_EXPECTED_RELEASE_DIGEST='+pins['release_digest']}
        mounts={(item['Name'],item['Destination'],item['RW']) for item in row['Mounts'] if item['Type']=='volume'}
        return (row['Image']==pins['image_id'] and expected_env<=env and config['User']=='10001:10001'
                and config['Entrypoint']==['/venv/bin/python']
                and config['Labels'].get('com.modular.job_template')==desired['template']
                and config['Cmd']==(['-m','modular_platform.recurrence_runner','--poll-seconds','.25'] if pool=='producer'
                    else ['-m','modular_platform.job_runner','--pool',pool,'--poll-seconds','.25'])
                and host['ReadonlyRootfs'] and host['NanoCpus']==spec['cpu_millis']*1000000
                and host['Memory']==spec['memory_mib']*1024**2 and host['PidsLimit']==128
                and host['CapDrop']==['ALL'] and 'no-new-privileges' in host['SecurityOpt']
                and host['RestartPolicy']['Name']=='unless-stopped' and config['StopTimeout']==spec['shutdown_seconds']
                and config.get('Healthcheck',{}).get('Test')==['CMD-SHELL',HEALTH_COMMAND]
                and all(item['Type'] in {'volume','tmpfs'} for item in row['Mounts'])
                and mounts=={(op.project+'_appconfig','/run/secrets',False),(op.project+'_filestore','/var/lib/modular',True)}
                and set(row['NetworkSettings']['Networks'])=={op.project+'_runtime'})

    def _healthy(self, row, desired):
        state=row['State']; health=state.get('Health',{})
        if not state['Running'] or state.get('Restarting') or health.get('Status')!='healthy' or not self._matches(row,desired):
            return False
        try:
            payload=json.loads(health['Log'][-1]['Output'])
            return (0<=time.time()-payload['updated_at']<=10 and payload['state'] in {'idle','running'}
                    and all(payload[key]==desired['pins'][key] for key in ('database','site_id','release_digest','inventory_digest'))
                    and payload['pool']==row['Config']['Labels']['com.modular.job_pool'])
        except (KeyError,IndexError,TypeError,ValueError):
            return False

    def status(self):
        desired=self.desired()
        lanes=self.operator._lanes()
        if not desired:
            return dict(event='job_fleet',state='unconfigured',pools={},lanes=[])
        expected=self._expected(desired)
        records=[dict(name=name,pool=row['Config']['Labels']['com.modular.job_pool'],container=row['Id'],
                      running=row['State']['Running'],ready=self._healthy(row,desired),
                      matches_profile=self._matches(row,desired)) for name,row in sorted(lanes.items())]
        pools={pool:dict(desired=desired['spec']['counts'].get(pool,0),
                        running=sum(row['running'] for row in records if row['pool']==pool),
                        ready=sum(row['ready'] for row in records if row['pool']==pool),
                        drained=sum(f'-job-{pool}-' in name for name in desired['drained_lanes'])) for pool in POOLS}
        ready={row['name'] for row in records if row['ready']}
        complete=expected==ready and set(lanes)==expected
        return dict(event='job_fleet',state='paused' if desired['state']=='paused' and not lanes else 'ready' if complete else 'partial',
                    generation=desired['generation'],approval=desired['approval'],pins=desired['pins'],pools=pools,lanes=records)

    def _stop(self, row, desired):
        op=self.operator
        grace=desired['spec']['shutdown_seconds']
        op.docker('update','--restart','no',row['Id'])
        if row['State']['Running']:
            op.docker('stop','--time',str(grace),row['Id'],timeout=grace+30)
        observed=json.loads(op.docker('inspect',row['Id']))[0]
        if observed['State']['Running'] or observed['State'].get('Restarting'):
            raise OperatorError('Managed lane still running after drain')
        op.docker('rm',row['Id'])

    def reconcile(self):
        op=self.operator
        desired=self.desired()
        if not desired:
            raise OperatorError('Review a worker profile before reconciliation')
        runtime=op.runtime()
        if desired['pins']!=self._pins(runtime):
            raise OperatorError('Worker profile is pinned to a different deployment release')
        lanes=op._lanes()
        accepted={desired['template'],*desired['accepted_templates']}
        if any(row['Config']['Labels'].get('com.modular.job_template') not in accepted for row in lanes.values()):
            raise OperatorError('Unrecognized worker template requires independent reconciliation')
        expected=self._expected(desired)
        if expected:self._check_authority(runtime,desired.get('recurrence_policy'))
        for name,row in lanes.items():
            if name not in expected or not self._matches(row,desired):
                self._stop(row,desired)
        if expected:
            result=op._run_admin(runtime,str(uuid4()),['dispatch'])
            if result!=dict(event='job_dispatch',site_id=op.site['site_id'],release_digest=desired['pins']['release_digest'],enabled=True):
                raise OperatorError('Enabled current dispatch required before starting managed lanes')
        lanes=op._lanes()
        for name in sorted(expected):
            row=lanes.get(name)
            if row:
                if not row['State']['Running']:op.docker('start',row['Id'])
                continue
            pool=name.rsplit('-job-',1)[1].rsplit('-',1)[0]
            base=op._base(runtime,name)
            base[base.index('--memory')+1]=str(desired['spec']['memory_mib'])+'m'
            pins=desired['pins']; spec=desired['spec']
            op.docker('run','-d','--restart','unless-stopped','--stop-timeout',str(spec['shutdown_seconds']),
                '--log-driver','local','--log-opt','max-size=2m','--log-opt','max-file=2',
                '--cpus',str(spec['cpu_millis']/1000),'--health-cmd',HEALTH_COMMAND,'--health-interval','3s',
                '--health-timeout','3s','--health-retries','2','--health-start-period','10s',
                '--label','com.modular.job_pool='+pool,'--label','com.modular.job_template='+desired['template'],
                '--env','MP_EXPECTED_SITE_ID='+pins['site_id'],'--env','MP_EXPECTED_RELEASE_DIGEST='+pins['release_digest'],
                *base,*(['-m','modular_platform.recurrence_runner','--poll-seconds','.25'] if pool=='producer'
                    else ['-m','modular_platform.job_runner','--pool',pool,'--poll-seconds','.25']))
        deadline=time.monotonic()+30
        while True:
            result=self.status()
            if result['state'] in {'ready','paused'} or time.monotonic()>=deadline:
                return result
            time.sleep(.5)

    def drain(self, *, pool=None, lane=None):
        desired=self.desired()
        if not desired:
            raise OperatorError('Managed drain requires a reviewed profile')
        if pool is None and lane is None:
            desired.update(state='paused')
        else:
            if pool not in POOLS or type(lane) is not int or not 1<=lane<=desired['spec']['counts'].get(pool,0):
                raise OperatorError('Exact configured pool and lane required')
            name=f'{self.operator.project}-job-{pool}-{lane}'
            desired['drained_lanes']=sorted(set(desired['drained_lanes'])|{name})
        self._save(desired)
        return self.reconcile()
