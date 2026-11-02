"""Bind actual source, notices, curated artifacts, runtime solution and retained build recipe."""
from datetime import datetime,timezone
import base64,hashlib,io,json,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g7-current-provenance-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import importlib.util
sp=importlib.util.spec_from_file_location('g7_static_provenance_context',OUTPUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUTPUT
load=f.load;guard=f.guard
from modular_platform.catalog import Catalog
from modular_platform.native_versions import corrected_parser
from modular import configuration
from build_distribution import seed_category_metadata

def digest(raw):return hashlib.sha256(raw).hexdigest()
def write(name,value):
    path=OUTPUT/name;assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n')

state,native=m.context();assert native.config['generation']==29;guard(state)
runtime=load(LOCAL/'runtime-observation.json');inventory=runtime['inventory'];index=load(OUTPUT/'runtime-license-index.json')
assert runtime['inventory_digest']==state['inventory_digest'] and not any(runtime[k] for k in ['modified_files','unexpected_addon_files','missing_addon_files'])
upstream=load(ROOT/'upstream.lock');base=upstream['commit'];assert inventory['policy']['upstream_commit']==base
assert subprocess.check_output(['git','remote','get-url','upstream']).decode().strip()==upstream['repository']
tree={}
for line in subprocess.check_output(['git','ls-tree','-r',base]).splitlines():
    info,name=line.split(b'\t',1);mode,kind,oid=info.split();
    if kind==b'blob':tree[name.decode()]=oid.decode()
names=[p for p in inventory['files'] if p in tree]
objects=subprocess.run(['git','cat-file','--batch'],input=''.join(tree[p]+'\n' for p in names).encode(),capture_output=True,check=True).stdout
buffer=io.BytesIO(objects);baseline={}
for p in names:
    oid,kind,size=buffer.readline().decode().split();assert kind=='blob' and oid==tree[p];raw=buffer.read(int(size));assert buffer.read(1)==b'\n';baseline[p]=raw
patches={p['path']:p for p in inventory['generated_patches']};differences=[]
for p,raw in baseline.items():
    if digest(raw)!=inventory['files'][p]:
        assert p in patches and digest(raw)==patches[p]['source_sha256'];differences.append(p)
assert set(differences)==set(patches)
assert digest(corrected_parser(baseline['odoo/tools/parse_version.py']))==inventory['files']['odoo/tools/parse_version.py']
with tempfile.TemporaryDirectory(prefix='mp-provenance-category-') as folder:
    category=Path(folder)/'category.xml';catalog=Path(folder)/'catalog.xml';category.write_bytes(baseline['odoo/addons/base/data/ir_module_category_data.xml']);catalog.write_bytes(baseline['odoo/addons/base/data/ir_module_module.xml'])
    seeded=seed_category_metadata(category,catalog);assert seeded==patches['odoo/addons/base/data/ir_module_category_data.xml']['seeded_categories'];assert digest(category.read_bytes())==inventory['files']['odoo/addons/base/data/ir_module_category_data.xml']
for p in ['LICENSE','COPYRIGHT']:
    assert (ROOT/p).read_bytes()==baseline[p] and digest(baseline[p])==inventory['files'][p]
write('official-source.json',dict(result='passed',upstream_commit=base,repository=upstream['repository'],official_files_physically_matched=len(names)-len(differences),exact_generated_exceptions=patches,generated_exceptions_reproduced=True,root_notices_exact=True,source_files={p:inventory['files'][p] for p in names}))

def norm(s):return re.sub('[-_.]+','-',s).lower()
def pins(path):return {norm(n):v for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)',path.read_text(),re.M)}
expected=pins(ROOT/'deploy/requirements-r1.lock')|pins(ROOT/'deploy/build-requirements.lock')
actual={norm(p['name']):p['version'] for p in index['python']};assert actual==expected,(set(actual)^set(expected))
assert index['runtime_requirement_lock_sha256']==digest((ROOT/'deploy/requirements-r1.lock').read_bytes())
assert all(p['license']=='LGPL-3' for p in index['native'])
assert all(p['copyright'] for p in index['os_packages'])
supplement=load(OUTPUT/'supplemental-notices.json');missing={p['name'] for p in index['python'] if not p['notices']}
assert missing=={p['name'] for p in supplement['packages']}=={'geoip2','pyserial','xlwt'}
notices=load(LOCAL/'collected-runtime-notices.json')['notices'];archive=io.BytesIO();notice_index=[]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path,item in sorted(notices.items()):
        raw=base64.b64decode(item['base64']);assert digest(raw)==item['sha256'];name='runtime'+path;z.writestr(name,raw);notice_index.append(dict(path=name,sha256=digest(raw),bytes=len(raw)))
    for package in supplement['packages']:
        for f in package['notices']:
            raw=(ROOT/f['path']).read_bytes();assert digest(raw)==f['sha256'];z.writestr(f['path'],raw);notice_index.append(dict(path=f['path'],sha256=f['sha256'],bytes=len(raw)))
    node=load(ROOT/'packages/host_sdk/package-lock.json');node_rows=[]
    for path,entry in node['packages'].items():
        if not path:continue
        assert entry['version']=='7.0.2' and entry['license']=='Apache-2.0' and entry['resolved'].startswith('https://registry.npmjs.org/')
        assert entry['integrity'].startswith('sha512-') and len(base64.b64decode(entry['integrity'][7:]))==64
        node_rows.append(dict(package=path,**entry))
    for name in ['typescript','@typescript/typescript-win32-x64']:
        root=ROOT/'packages/host_sdk/node_modules'/name;metadata=load(root/'package.json');assert metadata['version']=='7.0.2' and metadata['license']=='Apache-2.0'
        for p in root.iterdir():
            if p.is_file() and p.name in ['LICENSE','NOTICE.txt']:
                archive_name='build-node/'+name+'/'+p.name;raw=p.read_bytes();z.writestr(archive_name,raw);notice_index.append(dict(path=archive_name,sha256=digest(raw),bytes=len(raw)))
raw=archive.getvalue();(LOCAL/'release-notices.zip').write_bytes(raw)
write('notice-bundle.json',dict(result='passed_preserved',archive_sha256=digest(raw),files=notice_index,python_distributions=len(actual),OS_packages=len(index['os_packages']),native_addons=len(index['native']),supplemental_source_notices=len(supplement['packages']),build_node_packages=node_rows,limits=['Recorded license metadata and preserved notice text; no commercial relicensing or legal compatibility opinion.','Node dependencies are host SDK development/type-check tools, not a new browser runtime.','The notice bundle accompanies the immutable image; three exact source notices are also tracked under third_party/python.']))

catalog=Catalog(native.catalog_root,configuration(m.j.LOCAL/'operator/trust.json'),readonly=True);artifacts=[]
for descriptor in catalog.snapshot():
    artifact=descriptor['digest'];path=catalog.path(artifact);verified=catalog.validator.verify(path,expected_digest=artifact)
    with zipfile.ZipFile(path) as z:
        prefix=verified.manifest['plugin']['id']+'/'
        for filename in ['LICENSE','COPYRIGHT']:assert z.read(prefix+'notices/'+filename)==(ROOT/filename).read_bytes()
        provenance=json.loads(z.read(prefix+'provenance.json'));assert provenance['upstream_commit']==base
        for name,h in provenance['source_files'].items():assert digest(z.read(prefix+name))==h
    artifacts.append(dict(plugin_id=descriptor['plugin_id'],version=descriptor['version'],digest=artifact,license=verified.manifest['plugin']['license'],native_notice_roots_exact=True,provenance_files=len(provenance['source_files'])))
assert len(artifacts)==18
write('artifact-provenance.json',dict(result='passed',artifacts=artifacts,curated_policy_generation=12,current_native_addon_licenses='LGPL-3',moving_latest_used=False))

build=load(ROOT/'docs/evidence/G7/20261102-notes8-labels4-candidate-03/candidate-build.json')
derived=load(ROOT/'docs/evidence/G7/20261102-notes8-labels4-candidate-04/candidate-build.json')
assert derived['image_id']==state['image_id'] and derived['source_image_id']==build['image_id'] and derived['base_OS_Python_exact']
assert all(digest((ROOT/p).read_bytes())==h for p,h in build['source_sha256'].items())
recipe=ROOT/'.local/operator/build-contexts/20261102-notes8-labels4-candidate-04/Dockerfile';assert recipe.read_text()==derived['recipe']
current_info=json.loads(subprocess.check_output(['docker','image','inspect',state['image_id']]))[0]
parent_info=json.loads(subprocess.check_output(['docker','image','inspect',derived['base_image_id']]))[0]
assert current_info['RootFS']['Layers'][:len(parent_info['RootFS']['Layers'])]==parent_info['RootFS']['Layers']
from modular_platform.deployment import inspect_image
parent_runtime=inspect_image(derived['base_image_id']);assert parent_runtime['python_metadata']==runtime['python_metadata']
from modular_platform.release_staging import validate_plugin_core_stability
validate_plugin_core_stability(parent_runtime,runtime)
owned={}
for path,h in build['source_sha256'].items():
 mapped='addons/'+path.removeprefix('platform_addons/') if path.startswith('platform_addons/') else path
 if mapped in inventory['files']:
  assert inventory['files'][mapped]==h;owned[path]=dict(image_path=mapped,sha256=h)
locks=[ROOT/'upstream.lock',ROOT/'packages/host_sdk/package-lock.json',ROOT/'packages/host_sdk/package.json',*(ROOT/'deploy').glob('*.lock'),ROOT/'deploy/runtime.lock.json',ROOT/'deploy/host-toolchain.lock.json',ROOT/'deploy/Dockerfile',ROOT/'tools/build_distribution.py',ROOT/'tools/reference_package.py',ROOT/'services/document_stats/requirements.lock',ROOT/'services/document_stats/dependency-provenance.json',ROOT/'services/document_stats/Dockerfile']
host={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in (ROOT/'packages/platform_sdk').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
host['tools/modular.py']=digest((ROOT/'tools/modular.py').read_bytes())
write('build-provenance.json',dict(result='passed',source_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),upstream_commit=base,image_id=state['image_id'],inventory_digest=runtime['inventory_digest'],image_OS=current_info['Os'],architecture=current_info['Architecture'],Python=runtime['python'],runtime_file_count=len(inventory['files']),parent_image_id=derived['base_image_id'],compiler_source_record='docs/evidence/G7/20261102-notes8-labels4-candidate-03/candidate-build.json',exact_runtime_derivation='docs/evidence/G7/20261102-notes8-labels4-candidate-04/candidate-build.json',recipe_sha256=digest(recipe.read_bytes()),parent_layers_exact=True,parent_OS_Python_exact=True,curated_policy_generation=12,all_source_build_inputs_current=True,mapped_owned_source=owned,locks={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in locks},host_operator_source=host,host_vs_image_changed={p:h for p,h in host.items() if p in inventory['files'] and inventory['files'][p]!=h},limits=['App static provenance/notice/artifact review only; independent worker, final image/history/archive secrets, vulnerabilities, network, full fresh install/recovery and handoff remain G7.','No new image/build/operation/deployment. Compiler images already retired; build records and exact source/current parent/image retained.','Byte-identical recovery uses retained immutable image, not assumed binary-identical native recompilation.','Notice metadata/text preservation is not a legal relicensing/compatibility opinion.']))
guard(state)
print(json.dumps(dict(result='passed_current_app_static_provenance',official_files=len(names),Python=len(actual),artifacts=len(artifacts),notice_files=len(notice_index))))
