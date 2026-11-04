"""Current immutable source, complete dependency metadata and exact retained notices."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core23-provenance-01'
sys.path.insert(0,str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'))
from lifecycle import f,context,snapshot,worker
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_bytes())
def save(path,value):
    with path.open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')

f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==8 and not PRIVATE.exists()
protect_directory(PRIVATE)
before=snapshot(state,'core23-provenance-before');identity=worker(native,'core23-provenance-worker-before')
runtime=inspect_image(state['image_id']);save(PRIVATE/'runtime-observation.json',runtime)
base=load(ROOT/'.local/g7-core23-uninstall-image-03/base-runtime.json')
admission=load(ROOT/'docs/evidence/G7/20261104-core23-uninstall-image-03/candidate-admission.json')
assert runtime['inventory_digest']==state['inventory_digest']==admission['inventory_digest']
assert runtime['python_metadata']==base['python_metadata'] and runtime['python_lock_digest']==base['python_lock_digest']
assert not any(runtime[name] for name in ['modified_files','missing_addon_files','unexpected_addon_files'])
old=base['inventory']['files'];actual=runtime['inventory']['files']
changes={name:dict(previous=old.get(name),current=actual.get(name)) for name in old.keys()|actual.keys() if old.get(name)!=actual.get(name)}
assert set(changes)=={row['path'] for row in admission['source_changes']} and len(changes)==11
build=load(ROOT/'docs/evidence/G7/20261104-core23-uninstall-image-03/candidate-build.json')
assert build['dependency_base_image']==base['image_id'] if 'image_id' in base else build['dependency_base_image']=='sha256:ae8bb33d618305d2d2b000e94e98bf9180e7e8c550e566d0dce0f5c97a2dd73a'
assert all(sha((ROOT/name).read_bytes())==digest for name,digest in build['source_sha256'].items())
official=ROOT/'docs/evidence/G7/20261104-source-notices-01/official-source.json';proof=load(official)
assert all(actual[name]==digest for name,digest in proof['source_files'].items())
assert runtime['inventory']['generated_patches']==base['inventory']['generated_patches']
tree=ast.parse((ROOT/'docs/evidence/G7/20261102-current-provenance-01/collect.py').read_text())
code=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in node.targets))
name='mp-g7-core23-provenance-01'
args=['docker','run','--rm','--name',name,'--label','mp.disposable=core23-provenance','--log-driver','none',
      '--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
      '--memory','512m','--pids-limit','128','--entrypoint','/venv/bin/python',state['image_id'],'-B','-c',code]
with (PRIVATE/'collection.stdout').open('xb') as stdout,(PRIVATE/'collection.stderr').open('xb') as stderr:
    result=subprocess.run(args,stdout=stdout,stderr=stderr,timeout=90)
assert result.returncode==0,'Inspect retained collector diagnostics before any retry'
data=load(PRIVATE/'collection.stdout');notices=data.pop('notices')
prior=ROOT/'docs/evidence/G7/20261104-core22-provenance-01';previous=load(prior/'application-index.json')
assert data['python']==previous['python'] and len(data['python'])==77
assert data['os_packages']==previous['os_packages'] and len(data['os_packages'])==113
assert data['source_notices']==previous['source_notices']
old_native={row['addon']:row for row in previous['native']};new_native={row['addon']:row for row in data['native']}
assert new_native.keys()==old_native.keys() and len(new_native)==17
assert [key for key in old_native if new_native[key]!=old_native[key]]==['mp_core']
assert {k:v for k,v in new_native['mp_core'].items() if k!='manifest_sha256'}=={k:v for k,v in old_native['mp_core'].items() if k!='manifest_sha256'}
bundle=load(prior/'notice-bundle.json');archive=ROOT/'.local/g7-core22-provenance-01/application-notices.zip'
assert sha(archive.read_bytes())==bundle['archive_sha256']
with zipfile.ZipFile(archive) as z:
    assert set(z.namelist())=={row['path'] for row in bundle['files']}
    for row in bundle['files']:
        raw=z.read(row['path']);assert len(raw)==row['bytes'] and sha(raw)==row['sha256']
    for path,item in notices.items():
        raw=base64.b64decode(item['base64']);assert sha(raw)==item['sha256'] and z.read('runtime'+path)==raw
assert {row['name'] for row in data['python'] if not row['notices']}=={'geoip2','pyserial','xlwt'}
data.update(image_id=state['image_id'],inventory_digest=state['inventory_digest'],notice_files=len(notices),
            source_collection_sha256=sha((PRIVATE/'collection.stdout').read_bytes()))
save(OUT/'application-index.json',data)
save(OUT/'notice-binding.json',dict(result='passed_actual_core23_exact_retained_notice_bytes',
    archive=archive.relative_to(ROOT).as_posix(),archive_sha256=bundle['archive_sha256'],files=bundle['files'],
    no_duplicate_archive_created=True,metadata_notices= len(notices),supplements=3))
assert snapshot(state,'core23-provenance-after')==before and worker(native,'core23-provenance-worker-after')==identity
f.guard(state)
absent=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=30)
assert absent.returncode and b'no such' in absent.stderr.lower()
save(OUT/'source-dependency-binding.json',dict(result='passed_current_core23_actual_source_dependency_notice_binding',
    image_id=state['image_id'],inventory_digest=state['inventory_digest'],configuration_generation=8,source_changes=changes,
    complete_recorded_build_inputs_match_current_checkout=len(build['source_sha256']),
    dependency_base_image=build['dependency_base_image'],python_distributions=77,OS_packages=113,native_addons=17,
    actual_python_metadata_digests_and_lock_exact=True,actual_OS_copyright_and_python_notice_bytes_exact=True,
    official_source_proof=dict(path=official.relative_to(ROOT).as_posix(),sha256=sha(official.read_bytes()),
                               recorded_source_hashes_match=len(proof['source_files']),official_files_physically_matched=proof['official_files_physically_matched'],exact_generated_exceptions=len(proof['exact_generated_exceptions'])),
    generated_patches_exact=True,all17tables_worker_original_configuration_exact=True,
    collector_removed=True,new_images_volumes_networks=0,
    limits=['Actual current source/dependency/notice binding only; support/host/vendor obligation supplements and dated vulnerability dispositions remain separate requirements.',
            'No final OPS03, security, fresh reproducibility or complete G7 pass. Retained notice archive reused after exact content verification.']))
print(json.dumps(dict(result='core23_actual_source_and_notices_bound',source_changes=11,Python=77,OS=113,notices=len(bundle['files']))))
