"""Bind current immutable core22 bytes and notices to the qualified upstream proof."""
import ast,base64,hashlib,io,json,re,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path.cwd(); OUT=Path(__file__).parent; PRIVATE=ROOT/'.local/g7-core22-provenance-01'
sys.path.insert(0,str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'))
from lifecycle import f,context,snapshot,worker
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
f.OUTPUT=OUT; state,native=context('connector')
assert native.config['generation']==5 and not PRIVATE.exists(); protect_directory(PRIVATE)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_bytes())
def save(path,value):
 with path.open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
before=snapshot(state,'core22-provenance-before'); identity=worker(native,'core22-provenance-worker-before')
runtime=inspect_image(state['image_id']);save(PRIVATE/'runtime-observation.json',runtime)
old=load(ROOT/'.local/g7-release-runtime-audit-01/runtime-observation.json')
assert runtime['inventory_digest']==state['inventory_digest']
current=native.observer.read()
assert current['image_id']==state['image_id'] and not current['runtime']['modified_files']
previous=old['inventory']['files']; actual=runtime['inventory']['files']
assert set(previous)==set(actual)
changed={name:dict(previous=previous[name],current=actual[name]) for name in actual if previous[name]!=actual[name]}
assert set(changed)=={'addons/mp_core/__manifest__.py','packages/platform_sdk/modular_platform/projection.py'}
for name in changed:
 local=ROOT/('platform_addons/mp_core/__manifest__.py' if name.startswith('addons/') else name)
 assert sha(local.read_bytes())==actual[name]
official=ROOT/'docs/evidence/G7/20261104-source-notices-01/official-source.json'
proof=load(official)
assert all(actual[name]==digest for name,digest in proof['source_files'].items())
assert runtime['inventory']['generated_patches']==old['inventory']['generated_patches']
tree=ast.parse((ROOT/'docs/evidence/G7/20261102-current-provenance-01/collect.py').read_text())
code=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
name='mp-g7-core22-provenance-01'
args=['docker','run','--rm','--name',name,'--label','com.modular.disposable=mp-g7-core22-provenance','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--entrypoint','/venv/bin/python',state['image_id'],'-B','-c',code]
with (PRIVATE/'collection.stdout').open('xb') as stdout,(PRIVATE/'collection.stderr').open('xb') as stderr:
 result=subprocess.run(args,stdout=stdout,stderr=stderr,timeout=90)
assert result.returncode==0,'Inspect retained diagnostics, do not restart unchanged'
data=load(PRIVATE/'collection.stdout'); notices=data.pop('notices')
oldindex=load(ROOT/'docs/evidence/G7/20261103-release-runtime-audit-01/application-index.json')
assert data['os_packages']==[{k:v for k,v in p.items() if k not in ['source_package','source_version']} for p in oldindex['os_packages']]
def norm(value):return re.sub('[-_.]+','-',value).lower()
pins={norm(n):v for path in ['deploy/requirements-r1.lock','deploy/build-requirements.lock'] for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)',(ROOT/path).read_text(),re.M)}
assert {norm(p['name']):p['version'] for p in data['python']}==pins and len(pins)==77
assert data['runtime_requirement_lock_sha256']==sha((ROOT/'deploy/requirements-r1.lock').read_bytes())
assert {p['name'] for p in data['python'] if not p['notices']}=={'geoip2','pyserial','xlwt'}
new=next(p for p in data['python'] if norm(p['name'])=='defusedxml');assert new['version']=='0.7.1'
license_bytes=(ROOT/'third_party/python/defusedxml-0.7.1/LICENSE').read_bytes()
assert any(n['sha256']==sha(license_bytes) for n in new['notices'])
archive=io.BytesIO(); rows=[]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for path,item in sorted(notices.items()):
  raw=base64.b64decode(item['base64']);assert sha(raw)==item['sha256']
  name='runtime'+path;z.writestr(name,raw);rows.append(dict(path=name,sha256=sha(raw),bytes=len(raw)))
 supplements=load(ROOT/'docs/evidence/G5/20261029-provenance-01/supplemental-notices.json')
 for package in supplements['packages']:
  for item in package['notices']:
   raw=(ROOT/item['path']).read_bytes();assert sha(raw)==item['sha256']
   z.writestr(item['path'],raw);rows.append(dict(path=item['path'],sha256=sha(raw),bytes=len(raw)))
raw=archive.getvalue();(PRIVATE/'application-notices.zip').write_bytes(raw)
data.update(image_id=state['image_id'],inventory_digest=state['inventory_digest'],notice_files=len(notices),source_collection_sha256=sha((PRIVATE/'collection.stdout').read_bytes()))
save(OUT/'application-index.json',data)
save(OUT/'notice-bundle.json',dict(result='passed_current_core22_notices_preserved',archive_sha256=sha(raw),files=rows,python_distributions=77,OS_packages=len(data['os_packages']),native_addons=len(data['native']),defusedxml_license_matches_retained_source=True))
assert snapshot(state,'core22-provenance-after')==before and worker(native,'core22-provenance-worker-after')==identity;f.guard(state)
absent=subprocess.run(['docker','inspect','--type','container','mp-g7-core22-provenance-01'],capture_output=True,timeout=30);assert absent.returncode and b'no such' in absent.stderr.lower()
save(OUT/'qualification.json',dict(result='passed_core22_current_source_and_application_notice_delta',image_id=state['image_id'],inventory_digest=state['inventory_digest'],configuration_generation=5,source_changes=changed,official_source_proof=dict(path=official.relative_to(ROOT).as_posix(),sha256=sha(official.read_bytes()),all_recorded_source_hashes_match_current_inventory=True),copied_file_set_exact=True,generated_patches_exact=True,OS_package_versions_architecture_copyright_exact=True,python_distributions=77,notices='notice-bundle.json',fresh17tables_worker_and_original_configs_exact=True,collector_removed=True,images_built=0,limits=['Current application source and preserved notices only; full OPS03/license obligations, support/worker bundles, global secret/network/layer/history audits and second fresh build remain.','Earlier curated19 archive and host build-node notices retain their own byte-bound evidence; this does not imply they were reinstalled.']))
print(json.dumps(dict(result='core22_source_notices_passed',Python=77,OS=len(data['os_packages']),notices=len(rows),source_changes=len(changed))))
