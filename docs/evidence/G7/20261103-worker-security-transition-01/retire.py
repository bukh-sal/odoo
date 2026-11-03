"""Retire exact obsolete owned worker/runtime helpers after real job success."""
import hashlib,io,json,subprocess,sys,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import s,base,f,PRIVATE,OUT,PROJECT,VOLUME,IMAGE,op
state,native=s.context();job=f.load(PRIVATE/'remote-job.json');assert job['state']=='verified'
assert f.load(s.path('enable'))['state']=='verified'
before=base.snapshot(state,'worker-security-cleanup-before');current=base.worker(native,'worker-security-cleanup-worker-before')
assert current['image']==IMAGE
old=f.load(PRIVATE/'runtime-worker-before.json');oldconfig=f.load(PRIVATE/'runtime-config-before.json');volume=oldconfig['runtime']['public_config_volume'];oldproject=oldconfig['runtime']['project']
assert oldproject=='mp-disposable-document-stats-06' and volume==oldproject+'-public-config' and volume!=VOLUME
info=json.loads(f.command('worker-security-retire-old-inspect',['docker','inspect',old['container_id']]))[0]
assert info['Id']!=current['container_id'] and info['Image']==old['image'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
assert info['Config']['Labels']['com.docker.compose.project']==oldproject and len(info['Mounts'])==1 and info['Mounts'][0]['Name']==volume and not info['Mounts'][0]['RW']
v=json.loads(f.command('worker-security-retire-old-volume',['docker','volume','inspect',volume]))[0];assert v['Labels']['com.modular.disposable']==oldproject
code="import pathlib,tarfile,sys;r=pathlib.Path('/config');assert {p.name for p in r.iterdir()}=={'config.json','public.pem'};t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|');[t.add(r/n,arcname=n,recursive=False) for n in ['config.json','public.pem']];t.close()"
raw=f.command('worker-security-old-public-archive',['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/config,readonly','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code])
assert len(raw)<1048576
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as t:
 assert set(t.getnames())=={'config.json','public.pem'} and all(x.isfile() for x in t)
 config=json.loads(t.extractfile('config.json').read());assert config['endpoint_generation']==9 and config['key_id']=='recovery19-key'
 assert hashlib.sha256(t.extractfile('public.pem').read()).hexdigest()==old['public_digest']
archive=PRIVATE/'old06-public-config.tar';archive.write_bytes(raw);assert hashlib.sha256(archive.read_bytes()).digest()==hashlib.sha256(raw).digest()
f.command('worker-security-retire-old-container',['docker','rm',old['container_id']])
assert not f.command('worker-security-old-volume-unmounted',['docker','ps','-aq','--filter','volume='+volume]).strip()
f.command('worker-security-retire-old-public-volume',['docker','volume','rm',volume])
retired=[dict(id=old['container_id'],role='obsolete_worker06',exit_code=0)]
for action in ('suspend','upgrade','enable'):
 operation=f.load(s.path(action))['operation_id'];ids=f.command('worker-security-retire-'+action+'-list',['docker','ps','-aq','--filter','label=com.modular.operation='+operation]).decode().split()
 if not ids:continue
 rows=json.loads(f.command('worker-security-retire-'+action+'-inspect',['docker','inspect',*ids]))
 rows=[row for row in rows if row['Name'].lstrip('/').startswith(state['project']+'-op-'+operation+'-')]
 for index,row in enumerate(rows):
  assert row['Id'] not in {native.config['worker_id'],current['container_id']}
  assert row['Name'].lstrip('/').startswith(state['project']+'-op-'+operation+'-') and row['Config']['Labels']['com.modular.deployment']==native.config['deployment_id']
  assert row['Config']['Labels']['com.modular.operation']==operation and row['Image']==state['image_id'] and row['State']['Status']=='exited' and row['State']['ExitCode']==0
  f.command('worker-security-retire-'+action+'-'+str(index),['docker','rm',row['Id']]);retired.append(dict(id=row['Id'],role=action+'_terminal_helper',exit_code=0))
assert base.snapshot(state,'worker-security-cleanup-after')==before and base.worker(native,'worker-security-cleanup-worker-after')==current
f.save('retirement.json',dict(result='retired_exact_owned_obsolete_worker_and_terminal_helpers',containers=retired,public_volume_removed=volume,public_config_archive_sha256=hashlib.sha256(raw).hexdigest(),archive_verified_files=2,images_removed=0,networks_removed=0,current_runtime_data_exact=True,old_current_images_checkpoints_issuer_preserved=True))
print(json.dumps(dict(result='retired_and_preserved',containers=len(retired),public_volumes=1,images=0)))
