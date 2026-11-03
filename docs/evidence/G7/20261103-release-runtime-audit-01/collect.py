"""Current exact-image package/source/notice collection, no private mounts/network."""
import ast,base64,hashlib,importlib.util,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'))
from lifecycle import f,LOCAL as TARGET_LOCAL,context,snapshot,worker
from modular_platform.operator_os import protect_directory
from modular_platform.deployment import inspect_image
PRIVATE=ROOT/'.local/g7-release-runtime-audit-01';f.OUTPUT=OUT
def save(path,value):
 assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def run(label,args):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,cwd=ROOT,stdout=out,stderr=err,timeout=90)
 assert r.returncode==0,'Inspect exact retained diagnostics; no blind rerun';return (PRIVATE/(label+'.stdout')).read_bytes()
state,native=context('connector');assert native.config['generation']==4 and not PRIVATE.exists();protect_directory(PRIVATE)
before=snapshot(state,'release-audit-data-before');identity=worker(native,'release-audit-worker-before')
save(PRIVATE/'data-before.json',before);save(PRIVATE/'worker-before.json',identity)
runtime=inspect_image(native.config['image_id']);save(PRIVATE/'runtime-observation.json',runtime)
tree=ast.parse((OUT.parent/'20261102-current-provenance-01/collect.py').read_text())
base=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
base='import platform,ssl,zlib\n'+base
base=base.replace('print(json.dumps(dict(python=python','print(json.dumps(dict(runtime_components=dict(python=platform.python_version(),openssl=ssl.OPENSSL_VERSION,zlib=zlib.ZLIB_RUNTIME_VERSION),python=python')
records={}
for role,image,user in [('application',native.config['image_id'],'10001:10001'),('worker',identity['image'],'10002:10002')]:
 code=base
 if role=='worker':
  old="root=pathlib.Path('/opt/modular');inventory=json.loads((root/'distribution-inventory.json').read_text());notices={}"
  assert old in code;code=code.replace(old,"root=pathlib.Path('/app');inventory={'native_addons':[],'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}};notices={}")
  code=code.replace("(root/'requirements.lock')","(root/'provenance/requirements.lock')")
  code=code.replace('python=python,native=native','worker_source_files=inventory[\'files\'],python=python,native=native')
 name='mp-g7-release-audit-'+role+'-01'
 args=['docker','run','--rm','--name',name,'--label','com.modular.disposable=mp-g7-release-audit','--log-driver','none','--network','none','--read-only','--user',user,'--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--entrypoint','/venv/bin/python',image,'-B','-c',code]
 save(PRIVATE/(role+'-intent.json'),dict(name=name,image=image,collector_sha256=hashlib.sha256(code.encode()).hexdigest(),network='none',mounts=[]))
 raw=run(role+'-collection',args);data=json.loads(raw);notices=data.pop('notices')
 for notice in notices.values():assert hashlib.sha256(base64.b64decode(notice['base64'])).hexdigest()==notice['sha256']
 fmt='${Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\n'
 source=run(role+'-source-packages',['docker','run','--rm','--name',name+'-source-packages','--label','com.modular.disposable=mp-g7-release-audit','--log-driver','none','--network','none','--read-only','--user',user,'--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','dpkg-query',image,'-W','-f='+fmt])
 packages={}
 for line in source.decode().splitlines():
  package,version,arch,src,srcversion=line.split('\t');packages[package]=dict(version=version,architecture=arch,source_package=src,source_version=srcversion)
 for package in data['os_packages']:
  extra=packages[package['name']];assert package['version']==extra['version'] and package['architecture']==extra['architecture'];package.update(extra)
 assert len(packages)==len(data['os_packages'])
 data.update(result='collected_current_review_pending',utc=datetime.now(timezone.utc).isoformat(),image_id=image,notice_files=len(notices),raw_notice_bundle_sha256=hashlib.sha256(raw).hexdigest(),collector_auto_removed=True,limits=['Actual installed metadata/notices/source package inventory, not a security/license/reproducibility pass.','No private config/issuer/DB/operator mounts, network, plugin import or runtime restart.'])
 save(OUT/(role+'-index.json'),data);records[role]=dict(image=image,python=len(data['python']),OS=len(data['os_packages']),notices=len(notices),components=data['runtime_components'])
assert snapshot(state,'release-audit-data-after')==before and worker(native,'release-audit-worker-after')==identity;f.guard(state)
save(OUT/'collection.json',dict(result='current_exact_images_collected_review_pending',roles=records,original_protected_configs_exact=True,fresh17tables_worker_exact=True,images_built=0,retained_collectors=0))
print(json.dumps(dict(result='collected_current_images',roles=records)))
