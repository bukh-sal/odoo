"""One bounded worker image build; never start or reconfigure the worker."""
import hashlib,io,json,subprocess,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PRIVATE=ROOT/'.local/g7-worker-dependencies-image-01';assert PRIVATE.is_dir()
names=['services/document_stats/'+n for n in ['Dockerfile','__init__.py','engine.py','server.py','requirements.lock','dependency-provenance.json']]
names+=['packages/platform_sdk/modular_platform/'+n for n in ['__init__.py','contracts.py','tokens.py']]
names+=['packages/contracts/v1/'+n+'.schema.json' for n in ['worker-request','worker-response','worker-claims']]
names+=['LICENSE','COPYRIGHT'];sources={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
context=io.BytesIO()
with tarfile.open(fileobj=context,mode='w',format=tarfile.USTAR_FORMAT) as tar:
 for name in names:tar.add(ROOT/name,arcname='Dockerfile' if name.endswith('/Dockerfile') else name,recursive=False)
old=json.loads((PRIVATE/'state.json').read_text());assert old['state']=='building' and old['source_sha256']==sources
tag=old['tag'];assert subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode!=0
record=dict(state='building',tag=tag,diagnosed_previous='Docker rejected ambiguous stdin/-f context before any build; root Dockerfile standard tar and explicit buildx load selected',source_sha256=sources,context_sha256=hashlib.sha256(context.getvalue()).hexdigest())
(PRIVATE/'state.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
args=['docker','buildx','build','--load','--label','com.modular.disposable=mp-g7-worker-security','-t',tag,'-']
with (OUT/'build02.log').open('xb') as out:r=subprocess.run(args,input=context.getvalue(),stdout=out,stderr=subprocess.STDOUT,timeout=600)
assert r.returncode==0,'Inspect exact worker builder; never restart/rebuild blindly'
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in sources.items())
code="import importlib.metadata as m,importlib.util,json;assert importlib.util.find_spec('odoo') is None;v={d.metadata['Name']:d.version for d in m.distributions()};assert len(v)==13 and v['pip']=='26.3' and v['cryptography']=='50.0.2';print(json.dumps(v,sort_keys=True))"
r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--user','10002:10002','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',image,'-B','-c',code],capture_output=True,timeout=60)
(PRIVATE/'inventory.stdout').write_bytes(r.stdout);(PRIVATE/'inventory.stderr').write_bytes(r.stderr);assert r.returncode==0
record.update(state='built_not_started_not_approved',image_id=image,packages=json.loads(r.stdout),odoo_absent=True,command=args,existing_worker_unchanged=True,
 limits=['Candidate build/13distribution import inventory only; no approved worker transition, runtime tokens/HTTP/config/mount/resource/recovery/security qualification.'])
(PRIVATE/'state.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
with (OUT/'candidate-build.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2);f.write('\n')
print(json.dumps(dict(result=record['state'],image_id=image,packages=13)))
