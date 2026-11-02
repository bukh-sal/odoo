"""Install the one locally compiled, hashed wheel in the owned probe only."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-dependency-compatibility-01'
state=json.loads((PRIVATE/'probe-state.json').read_text())
assert state['state']=='native_primitives_passed_further_qualification_pending'
built=json.loads((OUT/'ldap-build.json').read_text());wheel=built['wheel']
data=(PRIVATE/'ldap-wheels'/wheel['filename']).read_bytes();assert hashlib.sha256(data).hexdigest()==wheel['sha256']
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w') as tar:
 for name,raw in [('ldap-wheel/'+wheel['filename'],data),('ldap-wheel/install.lock',('python-ldap==3.4.8 --hash=sha256:'+wheel['sha256']+'\n').encode())]:
  item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644;tar.addfile(item,io.BytesIO(raw))
load="import pathlib,sys,tarfile;root=pathlib.Path('/probe');assert not (root/'ldap-wheel').exists();t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|');[(t.extract(m,path=root,filter='data')) for m in t]"
common=['--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--cpus','2','--tmpfs','/tmp','--mount','type=volume,source='+state['volume']+',target=/probe','--entrypoint','/probe/venv/bin/python',state['image'],'-B']
def run(label,args,raw=None):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:
  r=subprocess.run(args,input=raw,stdout=out,stderr=err,timeout=120)
 assert r.returncode==0,'Inspect exact '+label+' result, do not replay'
run('ldap-wheel-load',['docker','run','--rm','-i',*common,'-c',load],archive.getvalue())
name=state['project']+'-ldap-install';state['ldap_install_container']=name;state['state']='ldap_install_running';(PRIVATE/'probe-state.json').write_text(json.dumps(state,indent=2)+'\n')
code="import subprocess,sys;assert sys.prefix=='/probe/venv';subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--find-links','/probe/ldap-wheel','--require-hashes','--upgrade','-r','/probe/ldap-wheel/install.lock'],check=True);subprocess.run([sys.executable,'-m','pip','check'],check=True)"
run('ldap-wheel-install',['docker','run','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none',*common,'-c',code])
state['state']='ldap_installed_native_probe_pending';state['deferred_source_build']=[];(PRIVATE/'probe-state.json').write_text(json.dumps(state,indent=2)+'\n')
(OUT/'ldap-install.json').write_text(json.dumps(dict(result='installed_in_isolated_probe_only',wheel=wheel,pip_check=True,volume=state['volume'],container=name,network='none',qualified_runtime_unchanged=True),indent=2)+'\n')
print('LDAP3.4.8 installed and pip check passed only in owned isolated VENV')
