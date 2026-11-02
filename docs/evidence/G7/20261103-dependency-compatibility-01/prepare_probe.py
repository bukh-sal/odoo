"""One isolated copied virtual environment; never alter the qualified runtime."""
import concurrent.futures,hashlib,io,json,re,subprocess,sys,tarfile,urllib.request
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-dependency-compatibility-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.operator_store import _write_new
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import parse_wheel_filename
from packaging.version import Version
selection=json.loads((OUT/'candidate-selection.json').read_text());runtime=json.loads((ROOT/'.local/g7-current-provenance-01/runtime-observation.json').read_text())
assert not (PRIVATE/'probe-state.json').exists();image=selection['base_image'];project='mp-g7-dep-'+uuid4().hex[:12]
record=dict(state='recorded_before_creation',project=project,volume=project+'-venv',image=image,copy_container=project+'-copy',install_container=project+'-install',deferred_source_build=['python-ldap'],no_original_venv_or_database_or_authority_mounts=True)
_write_new(PRIVATE/'probe-state.json',record)
def save(name,value):(PRIVATE/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def call(label,args,**kwargs):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,stdout=out,stderr=err,timeout=600,**kwargs)
 assert r.returncode==0,'Inspect exact isolated probe diagnostics; do not recreate or retry unchanged'
 return (PRIVATE/(label+'.stdout')).read_bytes()
def phase(value):record['state']=value;save('probe-state.json',record);print(json.dumps(dict(phase=value,project=project)),flush=True)
def norm(value):return re.sub('[-_.]+','-',value).lower()
metadata={norm(p['name']):dict(version=p['version'],requires_dist=p['requires_dist']) for p in runtime['python_metadata']};metadata.pop('pypdf2')
for p in selection['candidates']:metadata[norm(p['package'])]=dict(version=p['version'],requires_dist=p['requires_dist'])
conflicts=[]
for name,p in metadata.items():
 for declaration in p['requires_dist']:
  req=Requirement(declaration)
  if req.marker and not req.marker.evaluate({**runtime['markers'],'extra':''}):continue
  target=metadata.get(norm(req.name))
  if not target or Version(target['version']) not in req.specifier:conflicts.append(dict(package=name,requires=declaration,available=target))
save('candidate-constraint-check.json',dict(conflicts=conflicts,selected=len(metadata)));assert not conflicts
tags={tag:i for i,tag in enumerate(runtime['accepted_wheel_tags'])};wheels=[]
for p in selection['candidates']:
 if p['source_build_required']:continue
 def rank(f):return min(tags[str(t)] for t in parse_wheel_filename(f['filename'])[3] if str(t) in tags)
 wheel=min(p['compatible_wheels'],key=lambda f:(rank(f),f['filename']));wheels.append(dict(package=p['package'],version=p['version'],**wheel))
destination=PRIVATE/'wheels';destination.mkdir()
def download(wheel):
 assert wheel['url'].startswith('https://files.pythonhosted.org/packages/') and wheel['size']<100*1024*1024
 with urllib.request.urlopen(wheel['url'],timeout=60) as response:raw=response.read()
 assert len(raw)==wheel['size'] and hashlib.sha256(raw).hexdigest()==wheel['digests']['sha256']
 assert Path(wheel['filename']).name==wheel['filename'];(destination/wheel['filename']).write_bytes(raw)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download,wheels))
lock='\n'.join(p['package']+'=='+p['version']+' --hash=sha256:'+p['digests']['sha256'] for p in wheels)+'\n';(PRIVATE/'probe-requirements.lock').write_text(lock,encoding='utf8')
phase('creating_owned_venv_volume');call('create-volume',['docker','volume','create','--label','com.modular.disposable='+project,record['volume']])
copy="import os,pathlib,shutil;root=pathlib.Path('/probe');assert not list(root.iterdir());shutil.copytree('/venv',root/'venv',symlinks=True);[(os.lchown(p,10001,10001)) for p in [root,*(root.rglob('*'))]];print('copied isolated virtual environment only')"
phase('copying_readonly_base_environment')
call('copy-venv',['docker','run','--name',record['copy_container'],'--label','com.modular.disposable='+project,'--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+record['volume']+',target=/probe','--entrypoint','/venv/bin/python',image,'-B','-c',copy])
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w:gz') as tar:
 for p in destination.iterdir():tar.add(p,arcname='wheels/'+p.name,recursive=False)
 tar.add(PRIVATE/'probe-requirements.lock',arcname='probe-requirements.lock',recursive=False)
phase('loading_hashed_probe_wheels')
extract="import pathlib,sys,tarfile;root=pathlib.Path('/probe');t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz');[(t.extract(m,path=root,filter='data')) for m in t];print('loaded hashed probe wheels')"
call('load-wheels',['docker','run','--rm','-i','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+record['volume']+',target=/probe','--entrypoint','/venv/bin/python',image,'-B','-c',extract],input=archive.getvalue())
phase('installing_in_isolated_copy')
install="import json,subprocess,sys;assert sys.prefix=='/probe/venv';subprocess.run([sys.executable,'-m','pip','uninstall','-y','PyPDF2'],check=True);subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--find-links','/probe/wheels','--require-hashes','--upgrade','-r','/probe/probe-requirements.lock'],check=True);subprocess.run([sys.executable,'-m','pip','check'],check=True);print('MP_ISOLATED_DEPENDENCIES='+json.dumps({'prepared':True,'prefix':sys.prefix,'LDAP_source_build_deferred':True}))"
call('install-wheels',['docker','run','--name',record['install_container'],'--label','com.modular.disposable='+project,'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--cpus','2','--tmpfs','/tmp','--mount','type=volume,source='+record['volume']+',target=/probe','--entrypoint','/probe/venv/bin/python',image,'-B','-c',install])
phase('isolated_wheel_environment_prepared_native_probe_pending')
value=dict(result='prepared_isolated_dependency_compatibility_environment',project=project,volume=record['volume'],base_image=image,wheels=wheels,probe_lock_sha256=hashlib.sha256(lock.encode()).hexdigest(),original_runtime_unchanged=True,no_database_config_issuer_mounts=True,deferred_source_build=['python-ldap'],limits=['Compatibility experiment only; no selected deployment lock or security signoff.','python-ldap source build remains deferred to a controlled builder; the isolated copy still has old LDAP.','No application worker or service started; native primitive/API probes remain.'])
(OUT/'probe-preparation.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=value['result'],wheels=len(wheels),project=project)))
