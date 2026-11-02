"""Static no-network/no-private-mount provenance collection from the exact qualified image."""
from datetime import datetime,timezone
import base64,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from modular_platform.operator_os import protect_directory
from modular_platform.deployment import inspect_image
import importlib.util
sp=importlib.util.spec_from_file_location('g7_provenance_current',OUTPUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUTPUT
load=f.load

state,native=m.context();assert native.config['generation']==29 and load(m.MARKER)['state']=='qualified'
LOCAL=ROOT/'.local/g7-current-provenance-01';assert not LOCAL.exists();protect_directory(LOCAL)
runtime=inspect_image(state['image_id'])
(LOCAL/'runtime-observation.json').write_text(json.dumps(runtime,indent=2)+'\n')
before=m.snapshot(state,'g7-provenance-source-before');worker=m.worker(native,'g7-provenance-worker-before')
f.write(LOCAL/'source-data-before.json',before);f.write(LOCAL/'source-worker-before.json',worker)
name=state['project']+'-g7-provenance-static-01'
(LOCAL/'intent.json').write_text(json.dumps(dict(container=name,image_id=state['image_id'])))
code=r'''
import ast,base64,hashlib,importlib.metadata as m,json,pathlib,subprocess
root=pathlib.Path('/opt/modular');inventory=json.loads((root/'distribution-inventory.json').read_text());notices={}
def retain(path):
 raw=path.read_bytes();name=str(path);notices[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'base64':base64.b64encode(raw).decode()};return {'path':name,'sha256':notices[name]['sha256'],'bytes':len(raw)}
python=[]
for d in sorted(m.distributions(),key=lambda d:d.metadata['Name'].lower()):
 files=[]
 for entry in d.files or []:
  name=str(entry).lower();p=pathlib.Path(d.locate_file(entry))
  if p.is_file() and any(w in pathlib.PurePosixPath(name).name for w in ['license','licence','copying','copyright','notice']):files.append(retain(p))
 python.append(dict(name=d.metadata['Name'],version=d.version,license_expression=d.metadata.get('License-Expression'),license_field=d.metadata.get('License'),license_classifiers=[v for v in d.metadata.get_all('Classifier',[]) if v.startswith('License ::')],notices=files,metadata_sha256=hashlib.sha256(d.read_text('METADATA').encode()).hexdigest()))
native=[]
for name in sorted(inventory['native_addons']):
 path=root/('odoo/addons' if name=='base' else 'addons')/name/'__manifest__.py';v=ast.literal_eval(path.read_text());native.append(dict(addon=name,license=v.get('license','unspecified'),author=v.get('author'),manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
source_notices=[]
for name in sorted(inventory['files']):
 if any(w in pathlib.PurePosixPath(name).name.lower() for w in ['license','licence','copying','copyright','notice']):source_notices.append(retain(root/name))
os_packages=[]
raw=subprocess.check_output(['dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\n']).decode()
for line in raw.splitlines():
 name,version,arch=line.split('\t');copyright=pathlib.Path('/usr/share/doc')/name/'copyright';os_packages.append(dict(name=name,version=version,architecture=arch,copyright=retain(copyright) if copyright.is_file() else None))
print(json.dumps(dict(python=python,native=native,source_notices=source_notices,os_packages=os_packages,notices=notices,runtime_requirement_lock_sha256=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest())))
'''
args=['docker','run','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--entrypoint','/venv/bin/python',state['image_id'],'-B','-c',code]
r=subprocess.run(args,capture_output=True,timeout=60)
(LOCAL/'collection.stderr').write_bytes(r.stderr)
assert r.returncode==0,'Inspect retained container/static collector diagnostics before another attempt'
data=json.loads(r.stdout);(LOCAL/'collected-runtime-notices.json').write_bytes(r.stdout)
notices=data.pop('notices')
for item in notices.values():assert hashlib.sha256(base64.b64decode(item['base64'])).hexdigest()==item['sha256']
data.update(result='collected_review_required',utc=datetime.now(timezone.utc).isoformat(),image_id=state['image_id'],inventory_digest=runtime['inventory_digest'],files_physically_verified=len(runtime['inventory']['files']),container=name,notice_files=len(notices),notice_archive_sha256=hashlib.sha256(r.stdout).hexdigest(),limits=['Static installed metadata/notices inventory; license interpretation/obligations are not inferred from a green collector.','Official source/copy history, artifact license identity and lock matching are separate qualification steps.','No network, plugin imports, private mounts or deployment changes.'])
(OUTPUT/'runtime-license-index.json').write_text(json.dumps(data,indent=2)+'\n')
assert m.snapshot(state,'g7-provenance-source-after')==before and m.worker(native,'g7-provenance-worker-after')==worker
print(json.dumps(dict(result='collected_review_required',Python=len(data['python']),native=len(data['native']),OS=len(data['os_packages']),notices=len(notices))))
