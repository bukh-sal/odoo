"""Bind actual worker87 source/locks/base/notices before updating stale descriptor."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-runtime-audit-01'
def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(value):return re.sub('[-_.]+','-',value).lower()
index=load(OUT/'worker-index.json');build=load(OUT.parent/'20261103-worker-dependencies-image-01/candidate-build.json')
assert index['image_id']==build['image_id']=='sha256:87ad9d2d1c950cde6f6e233232ae2ae719d8df64601f0c7293e0a4b0be96e38f'
mapping={
 **{'services/document_stats/'+n:'services/document_stats/'+n for n in ['__init__.py','engine.py','server.py']},
 **{'packages/platform_sdk/modular_platform/'+n:'packages/platform_sdk/modular_platform/'+n for n in ['__init__.py','contracts.py','tokens.py']},
 **{'packages/contracts/v1/'+n:'packages/contracts/v1/'+n for n in ['worker-request.schema.json','worker-response.schema.json','worker-claims.schema.json']},
 'provenance/requirements.lock':'services/document_stats/requirements.lock','provenance/dependency-provenance.json':'services/document_stats/dependency-provenance.json','provenance/LICENSE':'LICENSE','provenance/COPYRIGHT':'COPYRIGHT'}
assert set(mapping)==set(index['worker_source_files'])
assert all(index['worker_source_files'][p]==sha(ROOT/source)==build['source_sha256'][source] for p,source in mapping.items())
pins={norm(n):v for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)',(ROOT/'services/document_stats/requirements.lock').read_text(),re.M)}
actual={norm(p['name']):p['version'] for p in index['python']};assert actual==pins and len(actual)==13
assert index['runtime_requirement_lock_sha256']==sha(ROOT/'services/document_stats/requirements.lock')
assert all(p['notices'] for p in index['python']) and all(p['copyright'] for p in index['os_packages'])
recipe=ROOT/'services/document_stats/Dockerfile';assert sha(recipe)==build['source_sha256']['services/document_stats/Dockerfile']
bases=re.findall(r'^FROM (\S+)',recipe.read_text(),re.M);assert len(bases)==2 and len(set(bases))==1
images=json.loads(subprocess.check_output(['docker','image','inspect',index['image_id'],bases[0]],timeout=20));image,base=images
assert image['Id']==index['image_id'] and image['RootFS']['Layers'][:len(base['RootFS']['Layers'])]==base['RootFS']['Layers']
assert image['Config']['User']=='10002:10002' and image['Config']['Entrypoint']==['/venv/bin/python','-m','services.document_stats.server']
lockpath=ROOT/'services/document_stats/image.lock.json';previous=load(lockpath);assert previous['image_id']=='sha256:5482020e027debc8a7b3d0a413e36417717b60642ea5b38e168aed328af5bbe0'
(PRIVATE/'previous-worker-image-lock.json').write_text(json.dumps(previous,indent=2)+'\n')
updated=dict(image_id=image['Id'],reference='modular-document-stats@'+image['Id'],base=bases[0],requirements_sha256=sha(ROOT/'services/document_stats/requirements.lock'),build_evidence='docs/evidence/G7/20261103-worker-dependencies-image-01/candidate-build.json',inventory='docs/evidence/G7/20261103-release-runtime-audit-01/worker-index.json',previous_image_id=previous['image_id'],previous_reference=previous['reference'],dependency_maintenance=dict(evidence='docs/evidence/G7/20261103-worker-security-transition-01/qualification.json',fresh_reference='docs/evidence/G7/20261103-fresh-target21-01/qualification.json',cryptography='50.0.2',pip='26.3',protocol_engine_schemas_unchanged=True,source_files_current=13),qualification='Actual approved runtime transition and fresh reference job qualified; final release advisory/license/network/secrets/reproducibility review remains.')
lockpath.write_text(json.dumps(updated,indent=2)+'\n')
report=dict(result='bound_actual_worker_source_lock_base_notices_and_updated_descriptor',image_id=image['Id'],source_files={s:dict(image_path=p,sha256=index['worker_source_files'][p]) for p,s in mapping.items()},base_image=bases[0],base_layers_exact=True,python_locked_packages=pins,all_python_OS_notice_bytes_retained=True,old_descriptor_image=previous['image_id'],new_descriptor_sha256=sha(lockpath),previous_descriptor_sha256=hashlib.sha256((json.dumps(previous,indent=2)+'\n').encode()).hexdigest(),descriptor_outside_image_build_context_inputs=True,runtime_changed=False,limits=['Static source/lock/base/notice binding, not full advisory/security/legal/reproducibility qualification.','Current old548 rollback image retained; no image/volume/runtime modification.'])
with (OUT/'worker-source-binding.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],packages=len(pins),files=len(mapping),runtime_changed=False)))
