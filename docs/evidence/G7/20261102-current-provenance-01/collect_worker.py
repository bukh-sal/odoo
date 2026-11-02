"""Collect exact independent worker metadata/notices offline, without config mounts."""
import ast,base64,hashlib,importlib.util,json,subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('worker_provenance_current',OUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==29
LOCAL=ROOT/'.local/g7-current-provenance-01';assert LOCAL.is_dir()
worker=m.worker(native,'g7-provenance-worker-collect-before');image=worker['image'];assert image=='sha256:5482020e027debc8a7b3d0a413e36417717b60642ea5b38e168aed328af5bbe0'
info=json.loads(subprocess.check_output(['docker','image','inspect',image],timeout=30))[0];assert info['Id']==image
f.write(LOCAL/'worker-image.json',info)
tree=ast.parse((OUT/'collect.py').read_text());code=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
old="root=pathlib.Path('/opt/modular');inventory=json.loads((root/'distribution-inventory.json').read_text());notices={}"
assert old in code
code=code.replace(old,"root=pathlib.Path('/app');inventory={'native_addons':[],'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}};notices={}")
code=code.replace("(root/'requirements.lock')","(root/'provenance/requirements.lock')")
code=code.replace("print(json.dumps(dict(python=python","print(json.dumps(dict(worker_source_files=inventory['files'],python=python")
name=state['project']+'-g7-worker-provenance-static-01';f.write(LOCAL/'worker-intent.json',dict(container=name,image=image,collector_sha256=hashlib.sha256(code.encode()).hexdigest(),network='none',mounts=[]))
r=subprocess.run(['docker','run','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none','--network','none','--read-only','--user','10002:10002','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--entrypoint','/venv/bin/python',image,'-B','-c',code],capture_output=True,timeout=60)
(LOCAL/'worker-collection.stderr').write_bytes(r.stderr);assert r.returncode==0,'Inspect original worker static collector; no blind replay'
(LOCAL/'collected-worker-notices.json').write_bytes(r.stdout);data=json.loads(r.stdout);notices=data.pop('notices')
for item in notices.values():assert hashlib.sha256(base64.b64decode(item['base64'])).hexdigest()==item['sha256']
assert m.worker(native,'g7-provenance-worker-collect-after')==worker
f.save('worker-runtime-license-index.json',dict(result='collected_review_required',**data,image_id=image,container=name,notice_files=len(notices),notice_archive_sha256=hashlib.sha256(r.stdout).hexdigest(),limits=['Static metadata/notices/source inventory only; current source/lock/notice provenance review and vulnerability qualification remain.','No network/config/issuer/private mounts, plugin imports, native operation or running-worker restart.']))
print(json.dumps(dict(result='worker_collected_review_required',Python=len(data['python']),OS=len(data['os_packages']),source_files=len(data['worker_source_files']),notices=len(notices))))
