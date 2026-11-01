"""Explicit operator projection into an existing, dedicated Linux Docker volume.

No worker launch, image pull or app database access. The caller's reviewed intent
precedes this mutation. On failure inspect that intent/volume; never auto-replay.
"""
import hashlib,json,os,re,subprocess
from pathlib import Path
from uuid import uuid4
from .operator_os import OperatorError,_not_link,verify_private_directory
from .contracts import load_json


SCRIPT=r'''
import hashlib,json,os,pathlib,stat,sys,uuid
v=json.load(sys.stdin);root=pathlib.Path('/projection');path=root/'authority.json'
assert set(v)=={'base','document','keys','mode'} and v['mode'] in ('publish','bootstrap')
for p in root.rglob('*'):
 assert not p.is_symlink() and (p.is_dir() or p.is_file()),'Unexpected projection object'
if v['mode']=='bootstrap':
 assert v['base'] is None and not list(root.iterdir()),'Bootstrap requires an empty volume'
 assert v['document']['generation']>=1,'Current independent authority required'
elif path.exists():
 old=json.loads(path.read_text())
 assert old==v['base'],'Current runtime projection differs; reconcile before any retry'
else:
 assert v['base']['generation']==0,'Runtime projection missing an existing generation'
if v['mode']=='publish':assert v['document']['generation']==v['base']['generation']+1
keys=root/'keys';keys.mkdir(exist_ok=True);keys.chmod(0o711);root.chmod(0o711)
for name,text in v['keys'].items():
 assert name.endswith('.pem') and '/' not in name and '\\' not in name
 p=keys/name;raw=text.encode()
 if p.exists():assert p.read_bytes()==raw,'Immutable runtime key reference differs'
 else:
  with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  p.chmod(0o440);os.chown(p,10001,0)
tmp=root/('authority.'+uuid.uuid4().hex+'.tmp')
with tmp.open('x') as f:json.dump(v['document'],f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
tmp.chmod(0o444);os.replace(tmp,path)
fd=os.open(root,os.O_RDONLY);os.fsync(fd);os.close(fd)
print(json.dumps(dict(generation=v['document']['generation'],state='projected')))
'''


class DockerWorkerProjection:
    def __init__(self,*,volume,deployment_id,helper_image,records):
        if not isinstance(volume,str) or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,120}',volume):raise OperatorError('Exact existing authority volume required')
        if not re.fullmatch('sha256:[0-9a-f]{64}',helper_image):raise OperatorError('Exact existing helper image required')
        self.volume,self.deployment_id,self.helper_image=volume,deployment_id,helper_image
        self.records=Path(records);verify_private_directory(self.records)
        self.descriptor=dict(kind='dedicated-docker-volume-v1',volume=volume,deployment_id=deployment_id,helper_image=helper_image,application_mount='/run/worker-authority',application_uid=10001,read_only=True)

    def _volume(self):
        raw=subprocess.run(['docker','volume','inspect',self.volume],capture_output=True,check=True,timeout=10).stdout
        info=load_json(raw)[0]
        if info['Name']!=self.volume or info.get('Labels',{}).get('com.modular.worker-authority')!=self.deployment_id:
            raise OperatorError('Dedicated operator-owned authority volume required')
        return info

    def observe_empty(self):
        info=self._volume()
        users=subprocess.run(['docker','ps','-aq','--filter','volume='+self.volume],capture_output=True,check=True,timeout=10).stdout.strip()
        if users:raise OperatorError('Replacement authority volume must have no attached containers')
        # Read-only, no network and no keys: refusal leaves the volume untouched.
        result=subprocess.run(['docker','run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL',
            '--mount','type=volume,source='+self.volume+',target=/projection,readonly','--entrypoint','/venv/bin/python',self.helper_image,
            '-c',"import pathlib;assert not list(pathlib.Path('/projection').iterdir())"],capture_output=True,timeout=20)
        if result.returncode:raise OperatorError('Replacement authority volume is not empty')
        return {k:info[k] for k in ['Name','CreatedAt','Driver','Labels']}

    def __call__(self,base,document,keys,operation):
        return self._project(base,document,keys,operation,'publish')

    def bootstrap(self,document,keys,operation):
        return self._project(None,document,keys,operation,'bootstrap')

    def _project(self,base,document,keys,operation,mode):
        self._volume()
        name='mp-worker-projection-'+operation.replace('-','')
        stdout=self.records/(operation+'.projection.stdout');stderr=self.records/(operation+'.projection.stderr')
        for path in [stdout,stderr]:_not_link(path)
        with stdout.open('xb') as out,stderr.open('xb') as err:
            result=subprocess.run(['docker','run','--rm','-i','--name',name,'--log-driver','none','--network','none',
                '--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--security-opt','no-new-privileges',
                '--memory','128m','--pids-limit','32','--mount','type=volume,source='+self.volume+',target=/projection',
                '--entrypoint','/venv/bin/python',self.helper_image,'-c',SCRIPT],
                input=json.dumps(dict(base=base,document=document,keys=keys,mode=mode)).encode(),stdout=out,stderr=err,timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:raise OperatorError('Runtime projection failed; inspect exact intent/diagnostics/volume without replay')
        if load_json(stdout.read_bytes())!={'generation':document['generation'],'state':'projected'}:raise OperatorError('Exact runtime projection receipt missing')
        return self.descriptor
