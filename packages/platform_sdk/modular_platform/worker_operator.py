"""Thin local operator adapter: worker publication and guarded native job process.

HTTP workers need no issuer mount. The saved original-actor job is reauthorized by
the inventoried runner; this adapter supplies only independently selected mounts
and current image/database/inventory pins. No artifact chooses these arguments.
"""
import hashlib,json,os,re,subprocess
from pathlib import Path
from uuid import UUID,uuid4
from .contracts import load_json
from .deployment import DockerObserver
from .operator_os import OperatorError,_not_link,verify_private_directory
from .plans import data_digest
from .worker_publication import WorkerAuthorityPublisher,DockerWorkerObservation
from .worker_projection import DockerWorkerProjection


def private_json(path):
    path=Path(path).absolute();verify_private_directory(path.parent);_not_link(path)
    if not path.is_file() or path.stat().st_size>1048576:raise OperatorError('Bounded independent worker configuration required')
    return load_json(path.read_bytes())


class WorkerOperator:
    def __init__(self,store,target_path,worker_path):
        self.store=store;self.target=private_json(target_path);DockerObserver(self.target)
        self.config=private_json(worker_path)
        required={'schema_version','deployment_id','site_id','runtime','authority_volume','helper_image'}
        c=self.config
        if not isinstance(c,dict) or set(c)!=required or c['schema_version']!=1 or c['deployment_id']!=self.target['deployment_id'] or c['helper_image']!=self.target['image_id']:
            raise OperatorError('Exact current independent worker/deployment configuration required')
        if len(self.target['sites'])!=1 or c['site_id']!=self.target['sites'][0]['site_id']:raise OperatorError('Exact single-site worker configuration required')
        self.publisher=WorkerAuthorityPublisher(store,c['deployment_id'],c['site_id'])
        self.sink=DockerWorkerProjection(volume=c['authority_volume'],deployment_id=c['deployment_id'],helper_image=c['helper_image'],records=self.publisher.records)
        self.publisher.sink=self.sink;self.observer=DockerWorkerObservation(c['runtime'])

    def review(self,operation):
        if str(UUID(operation))!=operation:raise OperatorError('Canonical publication operation required')
        path=self.publisher.records/(operation+'.plan.json');_not_link(path)
        plan=load_json(path.read_bytes())
        return dict(plan=plan,plan_hash=data_digest(plan))

    def provision(self,private_reference,public_reference,private_path,public_path):
        values=[]
        for path in [private_path,public_path]:
            path=Path(path).absolute();verify_private_directory(path.parent);_not_link(path)
            if not path.is_file() or path.stat().st_size>16384:raise OperatorError('Bounded independently provisioned key required')
            values.append(path.read_bytes())
        self.publisher.provision_keypair(private_reference,public_reference,*values)
        return dict(state='provisioned',private_reference=private_reference,public_reference=public_reference,public_digest=hashlib.sha256(values[1]).hexdigest())

    def publish(self,review,exact_hash,noninteractive):
        if review['plan'].get('kind')=='bootstrap':
            return self.publisher.publish_bootstrap(review,exact_hash=exact_hash,noninteractive=noninteractive)
        return self.publisher.publish(review,exact_hash=exact_hash,observer=self.observer,noninteractive=noninteractive)

    def _job_arguments(self,runtime,operation):
        files=runtime['inventory']['files']
        # Refuse old copied dispatch/bridge/runner code before any claim. The
        # current reviewed image must carry the same inventoried implementation.
        names=['job_runner.py','worker_start.py','worker_authority.py','worker_dispatch.py']
        for name in names:
            if files.get('packages/platform_sdk/modular_platform/'+name)!=hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest():
                raise OperatorError('Job dispatch requires a reviewed immutable image with current runner/authority source')
        source=Path(__file__).resolve().parents[3]
        addons=source/'platform_addons' if (source/'platform_addons').is_dir() else source/'addons'
        for name in ['job_dispatch.py','external_job.py','external_authority.py']:
            if files.get('addons/mp_core/'+name)!=hashlib.sha256((addons/'mp_core'/name).read_bytes()).hexdigest():
                raise OperatorError('Job dispatch requires the current inventoried native authority/bridge')
        project=self.target['project'];database=self.target['sites'][0]['database']
        return ['docker','run','--rm','--name',project+'-job-'+operation.replace('-',''),'--log-driver','none',
            '--label','com.modular.deployment='+self.target['deployment_id'],'--label','com.modular.job_operation='+operation,
            '--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp',
            '--memory','768m','--pids-limit','128','--network',project+'_runtime',
            '--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly',
            '--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular',
            '--mount','type=volume,source='+self.config['authority_volume']+',target=/run/worker-authority,readonly',
            '--env','MP_EXPECTED_DATABASE='+database,'--env','MP_EXPECTED_INVENTORY_DIGEST='+runtime['inventory_digest'],
            '--entrypoint','/venv/bin/python',self.target['image_id'],'-m','modular_platform.job_runner','--once']

    def run_once(self):
        self.publisher._authorize()
        observation=DockerObserver(self.target).read();runtime=observation['runtime'];operation=str(uuid4())
        arguments=self._job_arguments(runtime,operation)
        self.sink._volume()
        script="import json,pathlib;print(json.dumps(json.loads(pathlib.Path('/run/worker-authority/authority.json').read_text()),sort_keys=True))"
        raw=subprocess.run(['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL',
            '--mount','type=volume,source='+self.config['authority_volume']+',target=/run/worker-authority,readonly',
            '--entrypoint','/venv/bin/python',self.target['image_id'],'-c',script],capture_output=True,check=True,timeout=20).stdout
        if load_json(raw)!=self.publisher._document():raise OperatorError('Mounted worker authority differs from current independent publication')
        stdout=self.publisher.records/(operation+'.job.stdout');stderr=self.publisher.records/(operation+'.job.stderr')
        with stdout.open('xb') as out,stderr.open('xb') as err:
            result=subprocess.run(arguments,stdout=out,stderr=err,timeout=150,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:raise OperatorError('Guarded job process failed; inspect original job/claim and private diagnostics before another invocation')
        rows=[load_json(line) for line in stdout.read_bytes().splitlines() if line.startswith(b'{')]
        # Native bootstrap may write ordinary server logs; only the fixed runner's
        # minimized JSON records become local command output. No Note text/keys.
        allowed={'job_id','state','error_code','event','owner','database'}
        return dict(operation_id=operation,results=[{k:v for k,v in row.items() if k in allowed} for row in rows])
