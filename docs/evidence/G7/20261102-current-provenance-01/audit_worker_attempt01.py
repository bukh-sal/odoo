"""Bind the separate worker source/lock/base/notice inventory without restarting it."""
import base64,hashlib,importlib.util,json,re,subprocess,zipfile
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-current-provenance-01'
sp=importlib.util.spec_from_file_location('g7_worker_audit_context',OUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==29
index=f.load(OUT/'worker-runtime-license-index.json');raw=f.load(LOCAL/'collected-worker-notices.json');info=f.load(LOCAL/'worker-image.json')
def digest(value):return hashlib.sha256(value).hexdigest()
def norm(value):return re.sub('[-_.]+','-',value).lower()
mapping={
 **{'services/document_stats/'+name:'services/document_stats/'+name for name in ['__init__.py','engine.py','server.py']},
 **{'packages/platform_sdk/modular_platform/'+name:'packages/platform_sdk/modular_platform/'+name for name in ['__init__.py','contracts.py','tokens.py']},
 **{'packages/contracts/v1/'+name:'packages/contracts/v1/'+name for name in ['worker-request.schema.json','worker-response.schema.json','worker-claims.schema.json']},
 'provenance/requirements.lock':'services/document_stats/requirements.lock','provenance/dependency-provenance.json':'services/document_stats/dependency-provenance.json','provenance/LICENSE':'LICENSE','provenance/COPYRIGHT':'COPYRIGHT'}
assert set(mapping)==set(index['worker_source_files'])
for path,source in mapping.items():assert digest((ROOT/source).read_bytes())==index['worker_source_files'][path],path
pins={norm(n):v for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)',(ROOT/'services/document_stats/requirements.lock').read_text(),re.M)}
actual={norm(p['name']):p['version'] for p in index['python']};assert set(actual)-set(pins)=={'pip'} and all(actual[k]==v for k,v in pins.items())
assert index['runtime_requirement_lock_sha256']==digest((ROOT/'services/document_stats/requirements.lock').read_bytes())
closure=f.load(ROOT/'services/document_stats/dependency-provenance.json');assert closure['source_sha256']==digest((ROOT/closure['source']).read_bytes())
assert {norm(k):v['version'] for k,v in closure['packages'].items()}==pins
app={norm(p['name']):p['version'] for p in f.load(OUT/'runtime-license-index.json')['python']};assert all(app[k]==v for k,v in pins.items())
assert all(p['notices'] for p in index['python']) and all(p['copyright'] for p in index['os_packages'])
recipe=(ROOT/'services/document_stats/Dockerfile').read_text();bases=re.findall(r'^FROM (\S+)',recipe,re.M);assert len(bases)==2 and len(set(bases))==1
base=json.loads(subprocess.check_output(['docker','image','inspect',bases[0]],timeout=30))[0]
assert info['RootFS']['Layers'][:len(base['RootFS']['Layers'])]==base['RootFS']['Layers']
assert info['Config']['User']=='10002:10002' and info['Config']['Entrypoint']==['/venv/bin/python','-m','services.document_stats.server']
worker=m.worker(native,'g7-provenance-worker-audit-observation');assert worker['image']==index['image_id']==info['Id']
previous=f.load(OUT/'notice-bundle.json');source_zip=LOCAL/'release-notices.zip';assert digest(source_zip.read_bytes())==previous['archive_sha256']
destination=LOCAL/'release-notices-final.zip';assert not destination.exists();entries=[]
with zipfile.ZipFile(source_zip) as old,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as new:
 for entry in previous['files']:
  body=old.read(entry['path']);assert digest(body)==entry['sha256'];new.writestr(entry['path'],body);entries.append(entry)
 for path,item in sorted(raw['notices'].items()):
  body=base64.b64decode(item['base64']);assert digest(body)==item['sha256'];name='independent-worker'+path;new.writestr(name,body);entries.append(dict(path=name,sha256=digest(body),bytes=len(body)))
f.save('worker-provenance.json',dict(result='passed_current_worker_static_provenance',image_id=index['image_id'],base_image=bases[0],base_layers_exact=True,source_files={source:dict(image_path=path,sha256=index['worker_source_files'][path]) for path,source in mapping.items()},worker_recipe_sha256=digest(recipe.encode()),python_locked_subset=pins,bootstrap_pip=dict(version=actual['pip'],origin='venv ensurepip from exact digest-selected Python base; not a service runtime requirement'),OS_packages=len(index['os_packages']),python_distributions=len(actual),all_python_OS_notices_retained=True,running_worker_identity_publication_config_unchanged=True,limits=['Static source/dependency/notice provenance only; actual vulnerability/security qualification and fresh full release/recovery remain.','No worker restart/build/credential/endpoint or operation mutation.']))
f.save('notice-bundle-final.json',dict(result='passed_preserved_app_host_worker_notices',archive_sha256=digest(destination.read_bytes()),files=entries,app_and_host_files=len(previous['files']),independent_worker_files=len(raw['notices']),total_files=len(entries),limits=['Retains original installed/source license metadata and notice bytes; no legal compatibility/relicensing determination.','Current application/worker and host build notices only; fresh release artifact assembly/validation remains.']))
print(json.dumps(dict(result='passed_current_worker_static_provenance',locked_packages=len(pins),Python=len(actual),OS=len(index['os_packages']),notice_bundle_files=len(entries))))
