"""Local OS-authorized operator for pinned native job lanes."""
import hashlib
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from .contracts import load_json
from .deployment import DockerObserver
from .operator_os import OperationLocks,OperatorError,protect_directory
from .operator_store import _write_new
from .worker_operator import private_json


POOLS = {'urgent':1,'bulk':2}


class JobOperator:
    def __init__(self,store,target_path):
        self.store=store
        self.target=private_json(target_path)
        self.reader=DockerObserver(self.target)
        if len(self.target['sites'])!=1:
            raise OperatorError('Exact single-site managed job deployment required')
        self.site=self.target['sites'][0]
        self.project=self.target['project']
        self.deployment=self.target['deployment_id']
        self.records=protect_directory(store.root/'job-controls')

    @staticmethod
    def docker(*args,timeout=120):
        try:
            return subprocess.check_output(['docker',*args],stderr=subprocess.PIPE,timeout=timeout)
        except (subprocess.SubprocessError,OSError):
            raise OperatorError('Managed job Docker action failed; inspect owned containers and private intent') from None

    def _authorize(self):
        self.store._authorize_plan(dict(deployment_id=self.deployment,site_ids=[self.site['site_id']],
            policy_version=self.target['policy_version'],
            operator_authorization_generation=self.target['operator_authorization_generation']))

    def runtime(self):
        runtime=self.reader.read()['runtime']
        files=runtime['inventory']['files']
        for name in ('job_admin.py','job_runner.py','job_supervisor.py','worker_start.py','durable.py'):
            local=Path(__file__).with_name(name)
            if files.get('packages/platform_sdk/modular_platform/'+name)!=hashlib.sha256(local.read_bytes()).hexdigest():
                raise OperatorError('Managed jobs require the current reviewed runner and queue bytes')
        return runtime

    def _base(self,runtime,name):
        return ['--name',name,'--label','com.modular.deployment='+self.deployment,
            '--label','com.modular.job_site='+self.site['site_id'],'--read-only','--user','10001:10001',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp',
            '--memory','768m','--pids-limit','128','--network',self.project+'_runtime',
            '--mount','type=volume,source='+self.project+'_appconfig,target=/run/secrets,readonly',
            '--mount','type=volume,source='+self.project+'_filestore,target=/var/lib/modular',
            '--env','MP_EXPECTED_DATABASE='+self.site['database'],
            '--env','MP_EXPECTED_INVENTORY_DIGEST='+runtime['inventory_digest'],
            '--entrypoint','/venv/bin/python',self.target['image_id']]

    def _lanes(self):
        ids=self.docker('ps','-aq','--filter','label=com.modular.deployment='+self.deployment,
            '--filter','label=com.modular.job_site='+self.site['site_id'],
            '--filter','label=com.modular.job_pool').decode().split()
        if not ids:return {}
        result={}
        for row in load_json(self.docker('inspect',*ids)):
            name=row['Name'].lstrip('/')
            pool=row['Config']['Labels']['com.modular.job_pool']
            if pool not in POOLS or not re.fullmatch(re.escape(self.project+'-job-'+pool+'-')+r'[1-8]',name):
                raise OperatorError('Managed lane identity mismatch')
            result[name]=row
        return result

    def start(self,*,urgent_lanes=1,bulk_lanes=2):
        counts={'urgent':urgent_lanes,'bulk':bulk_lanes}
        if any(type(value) is not int or not 1<=value<=8 for value in counts.values()):
            raise OperatorError('Each managed pool requires one to eight lanes')
        runtime=self.runtime()
        found=self._lanes()
        requested={f'{self.project}-job-{pool}-{index}' for pool,count in counts.items()
                   for index in range(1,count+1)}
        if found.keys()-requested:
            raise OperatorError('Drain existing lanes before reducing a pool')
        result=[]
        for pool,count in counts.items():
            for index in range(1,count+1):
                name=f'{self.project}-job-{pool}-{index}'
                row=found.get(name)
                if row:
                    if row['Image']!=self.target['image_id']:
                        raise OperatorError('Drain and remove prior-release lanes before starting the selected image')
                    if not row['State']['Running']:self.docker('start',row['Id'])
                    ident=row['Id']
                else:
                    ident=self.docker('run','-d','--restart','unless-stopped','--stop-timeout','45',
                        '--log-driver','local','--log-opt','max-size=2m','--log-opt','max-file=2',
                        '--cpus','1','--label','com.modular.job_pool='+pool,*self._base(runtime,name),
                        '-m','modular_platform.job_runner','--pool',pool,'--poll-seconds','.25').decode().strip()
                result.append(dict(container=ident,pool=pool,name=name))
        return dict(state='started',lanes=result)

    def drain(self):
        found=self._lanes()
        running=[row['Id'] for row in found.values() if row['State']['Running']]
        if running:self.docker('stop','--time','45',*running)
        if found:self.docker('rm',*[row['Id'] for row in found.values()])
        return dict(state='drained',lanes=len(found))

    def admin(self,command,*,job=None,action=None,evidence=None,approval=None):
        runtime=self.runtime()
        attempt=str(uuid4())
        argv=[command]
        for key,value in (('job',job),('action',action),('evidence',evidence),('approval',approval)):
            if value is not None:argv.extend(['--'+key,value])
        if command=='apply':
            if not approval or not re.fullmatch(r'sha256:[0-9a-f]{64}',approval):
                raise OperatorError('Exact reviewed decision digest required')
            record=self.records/(approval[7:]+'.intent.json')
            if record.exists():
                raise OperatorError('Review already attempted; reconcile the recorded intent before another action')
            _write_new(record,dict(attempt=attempt,site=self.site['site_id'],job=job,
                                   action=action,evidence=evidence,approval=approval))
        raw=self.docker('run','--rm','--log-driver','none',
            *self._base(runtime,self.project+'-job-control-'+attempt.replace('-','')),
            '-m','modular_platform.job_admin',*argv)
        rows=[load_json(line) for line in raw.splitlines() if line.startswith(b'{')]
        if len(rows)!=1:
            raise OperatorError('Exact managed job operator result required')
        if command=='apply':_write_new(self.records/(approval[7:]+'.result.json'),rows[0])
        return rows[0]

    def run(self,command,**options):
        with OperationLocks(self.store.root/'locks',self.deployment,[self.site['site_id']]):
            self._authorize()
            if command=='start':return self.start(**options)
            if command=='drain':return self.drain()
            return self.admin(command,**options)
