"""Bind actual source, notices, curated artifacts, runtime solution and retained build recipe."""
from datetime import datetime,timezone
import base64,hashlib,io,json,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-provenance'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from clean_recovery_fixture import load,guard
from modular_platform.catalog import Catalog
from modular_platform.native_versions import corrected_parser
from modular import configuration
from build_distribution import seed_category_metadata

def digest(raw):return hashlib.sha256(raw).hexdigest()
def write(name,value):
    path=OUTPUT/name;assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n')

state=load(ROOT/'.local/g5-clean-recovery/state.json');guard(state)
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

catalog=Catalog(ROOT/'.local/g5-clean-recovery/operator/catalog',configuration(ROOT/'.local/g5-clean-recovery/operator/trust.json'),readonly=True);artifacts=[]
for descriptor in catalog.snapshot():
    artifact=descriptor['digest'];path=catalog.path(artifact);verified=catalog.validator.verify(path,expected_digest=artifact)
    with zipfile.ZipFile(path) as z:
        prefix=verified.manifest['plugin']['id']+'/'
        for filename in ['LICENSE','COPYRIGHT']:assert z.read(prefix+'notices/'+filename)==(ROOT/filename).read_bytes()
        provenance=json.loads(z.read(prefix+'provenance.json'));assert provenance['upstream_commit']==base
        for name,h in provenance['source_files'].items():assert digest(z.read(prefix+name))==h
    artifacts.append(dict(plugin_id=descriptor['plugin_id'],version=descriptor['version'],digest=artifact,license=verified.manifest['plugin']['license'],native_notice_roots_exact=True,provenance_files=len(provenance['source_files'])))
assert len(artifacts)==8
write('artifact-provenance.json',dict(result='passed',artifacts=artifacts,curated_policy_generation=4,current_native_addon_licenses='LGPL-3',moving_latest_used=False))

build=load(ROOT/'docs/evidence/G5/20261029-worker-fence-01/candidate-build.json');parent=load(ROOT/'docs/evidence/G5/20261029-permission-upgrade-01/image.json');assert build['image_id']==state['image_id'] and build['base_image_id']==parent['image_id']
recipe=ROOT/'.local/operator/build-contexts/worker-fence-01';recipe_hashes={}
for name,h in build['recipe_sha256'].items():assert digest((recipe/name).read_bytes())==h;recipe_hashes[name]=h
current_info=json.loads(subprocess.check_output(['docker','image','inspect',state['image_id']]))[0];parent_info=json.loads(subprocess.check_output(['docker','image','inspect',parent['image_id']]))[0]
assert current_info['RootFS']['Layers'][:len(parent_info['RootFS']['Layers'])]==parent_info['RootFS']['Layers']
assert inventory['files'][build['expected_changed_file']]==build['candidate_source_sha256']
for p,h in parent['source_sha256'].items():
    if p in inventory['files'] and p!=build['expected_changed_file']:assert inventory['files'][p]==h
locks=[ROOT/'upstream.lock',ROOT/'packages/host_sdk/package-lock.json',ROOT/'packages/host_sdk/package.json',*(ROOT/'deploy').glob('*.lock'),ROOT/'deploy/runtime.lock.json',ROOT/'deploy/Dockerfile',ROOT/'tools/build_distribution.py',ROOT/'tools/reference_package.py']
host={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in (ROOT/'packages/platform_sdk').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
host['tools/modular.py']=digest((ROOT/'tools/modular.py').read_bytes())
write('build-provenance.json',dict(result='passed',source_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),upstream_commit=base,image_id=state['image_id'],inventory_digest=runtime['inventory_digest'],image_OS=current_info['Os'],architecture=current_info['Architecture'],Python=runtime['python'],runtime_file_count=len(inventory['files']),parent_image_id=parent['image_id'],parent_build_record='docs/evidence/G5/20261029-permission-upgrade-01/image.json',parent_source_base=parent['git_base'],worker_overlay_record='docs/evidence/G5/20261029-worker-fence-01/candidate-build.json',overlay_recipe_sha256=recipe_hashes,parent_layers_exact=True,locks={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in locks},host_operator_source=host,host_vs_image_changed={p:h for p,h in host.items() if p in inventory['files'] and inventory['files'][p]!=h},limits=['No new image build, install, upgrade or traffic mutation. Static provenance qualification reuses already qualified fresh initialization/restore.','Source builds of native extensions can vary in binary bytes across compiler environments; exact release recovery uses retained immutable image, not an assumed byte-identical recompilation.','Host recovery CLI is separately versioned and owner-operated. Current host-only fixes intentionally differ from old unused executor files inside the immutable application image; no worker acquires operator authority.','G7 must refresh this provenance for the final G6/R1 image and run final reinstall, security/vulnerability and network qualification.']))
guard(state)
print(json.dumps(dict(result='passed_static_provenance',official_files=len(names),Python=len(actual),artifacts=len(artifacts),notice_files=len(notice_index))))
