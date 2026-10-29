"""An accessible rw volume still denies application UID access to operator data."""
from datetime import datetime,timezone
import json,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-operator-isolation'
INIT=r'''import hashlib,json,os,pathlib,sys,uuid
sys.path.insert(0,'/audit/packages/platform_sdk')
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import current_identity
root=pathlib.Path('/operator-probe/control');store=OperatorStore.initialize(root,{str(uuid.uuid4()):[str(uuid.uuid4())]})
for name in ['executor-secret','checkpoint.dump']:
 fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(b'SYNTHETIC_PRIVATE_PROBE_CONTENT_ONLY')
print(json.dumps({'state':'initialized','operator_identity':current_identity(),'owner_uid':root.stat().st_uid,'mode':oct(root.stat().st_mode&0o777),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}}))
'''
PROBE=r'''import errno,json,os,pathlib,sys
sys.path.insert(0,'/audit/packages/platform_sdk')
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError,current_identity
root=pathlib.Path('/operator-probe/control');result={'application_identity':current_identity(),'uid':os.geteuid(),'access':[]}
for name in ['policy.json','control.sqlite3','executor-secret','checkpoint.dump']:
 for action,flags in [('read',os.O_RDONLY),('write',os.O_WRONLY)]:
  try:fd=os.open(root/name,flags);os.close(fd);result['access'].append({'name':name,'action':action,'allowed':True})
  except OSError as error:result['access'].append({'name':name,'action':action,'allowed':False,'errno':error.errno})
try:os.listdir(root);result['list_allowed']=True
except OSError as error:result['list_allowed']=False;result['list_errno']=error.errno
try:fd=os.open(root/'forged-approval.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd);result['forge_allowed']=True
except OSError as error:result['forge_allowed']=False;result['forge_errno']=error.errno
try:OperatorStore(root);result['operator_store_open_allowed']=True
except OperatorError as error:result['operator_store_open_allowed']=False;result['store_refusal']=str(error)
assert result['uid']==10001 and all(not a['allowed'] and a['errno']==errno.EACCES for a in result['access']) and not result['list_allowed'] and not result['forge_allowed'] and result['forge_errno']==errno.EACCES and not result['operator_store_open_allowed']
print(json.dumps(result))
'''
VERIFY=r'''import hashlib,json,pathlib,sys
sys.path.insert(0,'/audit/packages/platform_sdk')
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import current_identity
root=pathlib.Path('/operator-probe/control');store=OperatorStore(root)
print(json.dumps({'state':'verified','operator_identity':current_identity(),'owner_uid':root.stat().st_uid,'mode':oct(root.stat().st_mode&0o777),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}}))
'''

def main():
 dest=OUTPUT/'foreign-UID-denial.json';marker=LOCAL/'linux-fixture.json';assert LOCAL.exists() and not marker.exists() and not dest.exists();target=json.loads((ROOT/'.local/g5-httpsecurity/operator/target.json').read_text());suffix=uuid4().hex[:10];volume=target['project']+'_operator_denial_'+suffix;record=dict(state='intent',project=target['project'],volume=volume,image_id=target['image_id'],containers=[]);marker.write_text(json.dumps(record,indent=2),encoding='utf8');r=subprocess.run(['docker','volume','create','--label','com.modular.disposable=true','--label','com.modular.purpose=operator-uid-denial',volume],capture_output=True,timeout=20);assert r.returncode==0
 def run(purpose,uid,code):
  name=target['project']+'-operator-denial-'+suffix+'-'+purpose;record['containers'].append(dict(name=name,purpose=purpose,state='intent'));marker.write_text(json.dumps(record,indent=2),encoding='utf8');args=['docker','run','--name',name,'--log-driver','none','--network','none','--read-only','--user',uid,'--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--tmpfs','/tmp:rw,nosuid,nodev,size=32m,mode=1777','--mount','type=volume,source='+volume+',target=/operator-probe']
  for source,dest in [('packages/platform_sdk','/audit/packages/platform_sdk'),('packages/contracts','/audit/packages/contracts')]:args+=['--mount','type=bind,source='+str(ROOT/source)+',target='+dest+',readonly']
  args+=['--entrypoint','/venv/bin/python',target['image_id'],'-B','-c',code];r=subprocess.run(args,capture_output=True,timeout=60);(LOCAL/(purpose+'.stdout')).write_bytes(r.stdout);(LOCAL/(purpose+'.stderr')).write_bytes(r.stderr);assert r.returncode==0,'Inspect exact retained fixture container/marker; no automatic reinitialization';value=json.loads(r.stdout);info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['State']['Running'] and info['State']['ExitCode']==0 and next(m for m in info['Mounts'] if m['Destination']=='/operator-probe')['RW'];record['containers'][-1].update(container_id=info['Id'],state='terminal_pass');marker.write_text(json.dumps(record,indent=2),encoding='utf8');return value
 before=run('initialize','0:0',INIT);assert before['owner_uid']==0 and before['mode']=='0o700';denial=run('application','10001:10001',PROBE);after=run('verify','0:0',VERIFY);assert before['files']==after['files'] and after['operator_identity']=='posix-uid:0';record.update(state='qualified',all_stopped=True);marker.write_text(json.dumps(record,indent=2),encoding='utf8')
 report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),fixture=record,operator_before=before,application=denial,operator_after=after,private_bytes_exact=True,volume_mounted_readwrite_for_denial=True,limits=['Synthetic standalone operator store/backup/secret fixture only. No real host store, database, runtime config or TLS key mounted or modified.','Kernel EACCES and SDK owner checks proven with UID10001 against owner UID0/mode0700, despite rw volume.','Real Windows stores are audited separately; this does not claim Windows impersonation or a native plugin data sandbox.'])
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',UID=10001,kernel_denied=len(denial['access']),forge_denied=True,private_bytes_exact=True,containers=3)))
if __name__=='__main__':main()
