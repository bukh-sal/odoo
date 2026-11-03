"""Actual deployed application identity/mount/capability and access-denial proof."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import DockerObserver
PROBE=r'''import errno,json,os,pathlib,shutil,socket,uuid
result={'uid':os.geteuid(),'gid':os.getegid(),'docker_cli_available':shutil.which('docker') is not None,'docker_host_configured':bool(os.environ.get('DOCKER_HOST')),'access':[]}
status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
result.update(cap_eff=int(status['CapEff'].strip(),16),no_new_privs=int(status['NoNewPrivs'].strip()))
paths=['/run/modular-operator/policy.json','/run/modular-operator/control.sqlite3','/run/modular-operator/checkpoints/private.dump','/etc/mp-tls/server.key','/var/run/docker.sock','/run/docker.sock','/host_mnt/c/Users/mesh/Documents/modular_platform/.local/operator/control/control.sqlite3','/run/desktop/mnt/host/c/Users/mesh/Documents/modular_platform/.local/operator/trust.json']
for path in paths:
 for mode,flags in [('read',os.O_RDONLY),('write',os.O_WRONLY)]:
  try:fd=os.open(path,flags);os.close(fd);result['access'].append({'path':path,'mode':mode,'allowed':True})
  except OSError as error:result['access'].append({'path':path,'mode':mode,'allowed':False,'errno':error.errno})
try:os.setuid(0);result['uid_elevation_allowed']=True
except OSError as error:result['uid_elevation_allowed']=False;result['uid_elevation_errno']=error.errno
path='/run/modular-operator-probe-'+uuid.uuid4().hex
try:os.mkdir(path);os.rmdir(path);result['control_namespace_creation_allowed']=True
except OSError as error:result['control_namespace_creation_allowed']=False;result['control_namespace_errno']=error.errno
print(json.dumps(result))
'''

def main():
 dest=OUTPUT/'application-identities.json';assert not dest.exists();results=[]
 for name,path in [('current-core22','.local/g7-fresh-release-01/target21/operator/target.json'),('preserved-original-core21','.local/g6-events/operator/target.json')]:
  config=json.loads((ROOT/path).read_text());cid=DockerObserver(config)._container('app');info=json.loads(subprocess.check_output(['docker','inspect',cid]))[0];host=info['HostConfig'];assert info['State']['Running'] and info['Config']['User']=='10001:10001' and host['ReadonlyRootfs'] and not host['Privileged'] and 'ALL' in host['CapDrop'] and any(s.startswith('no-new-privileges') for s in host['SecurityOpt']) and host['PidMode']!='host' and host['IpcMode']!='host' and host['NetworkMode']!='host' and not host.get('Devices')
  mounts=info['Mounts'];assert {m['Destination'] for m in mounts}=={'/var/lib/modular','/run/secrets'} and all(m['Type']=='volume' for m in mounts);assert all(m['Name']==config['project']+('_appconfig' if m['Destination']=='/run/secrets' else '_filestore') for m in mounts);assert not next(m for m in mounts if m['Destination']=='/run/secrets')['RW']
  observed=json.loads(subprocess.check_output(['docker','exec',cid,'/venv/bin/python','-c',PROBE],timeout=30));assert observed['uid']==10001 and observed['gid']==10001 and observed['cap_eff']==0 and observed['no_new_privs']==1 and not observed['docker_cli_available'] and not observed['docker_host_configured'] and not observed['uid_elevation_allowed'] and not observed['control_namespace_creation_allowed'] and all(not a['allowed'] for a in observed['access'])
  results.append(dict(target=name,container_id=info['Id'],generation=config['generation'],image=info['Image'],configuration_sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),namespace='private container; operator host roots and private TLS domain absent',mounts=[dict(destination=m['Destination'],volume=m['Name'],writable=m['RW']) for m in mounts],read_only_rootfs=True,privileged=False,cap_drop=host['CapDrop'],security_options=host['SecurityOpt'],host_pid_ipc_network=False,observed=observed));print(json.dumps(dict(target=name,result='passed',uid=observed['uid'],denied_accesses=len(observed['access']))),flush=True)
 report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),targets=results,limits=['Missing operator paths prove mount/namespace separation; a separate rw-volume/foreign-UID fixture proves permission denial.','The app legitimately reads its own restricted application DB configuration and writes its data/session volume; these are distinct from privileged host approval/backup/TLS stores.','Native Python remains trusted for application data; no general native-code sandbox claim.'])
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
