"""Current immutable source/notice proof; no runtime or release build mutation."""
import base64,hashlib,io,json,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUTPUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-source-notices-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,LOCAL as TARGET_LOCAL
from modular_platform.operator_os import protect_directory
from modular_platform.native_versions import corrected_parser
from modular_platform.catalog import Catalog
from modular import configuration
from build_distribution import seed_category_metadata
assert not LOCAL.exists();protect_directory(LOCAL);f.OUTPUT=OUTPUT
state,native=context('connector');assert native.config['generation']==4
load=lambda p:json.loads(p.read_text());runtime=load(ROOT/'.local/g7-release-runtime-audit-01/runtime-observation.json');inventory=runtime['inventory'];index=load(ROOT/'docs/evidence/G7/20261103-release-runtime-audit-01/application-index.json')
assert state['image_id']==index['image_id'] and state['inventory_digest']==runtime['inventory_digest']
# Verify actual current running immutable source before reusing exact static bytes.
current=native.observer.read();assert current['image_id']==state['image_id'] and current['runtime']['inventory_digest']==runtime['inventory_digest'] and not current['runtime']['modified_files']
def digest(raw):return hashlib.sha256(raw).hexdigest()
def write(name,value):
 path=OUTPUT/name;assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n')
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
supplement=load(ROOT/'docs/evidence/G5/20261029-provenance-01/supplemental-notices.json');missing={p['name'] for p in index['python'] if not p['notices']}
assert missing=={p['name'] for p in supplement['packages']}=={'geoip2','pyserial','xlwt'}
notices=load(ROOT/'.local/g7-release-runtime-audit-01/application-collection.stdout')['notices'];archive=io.BytesIO();notice_index=[]
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

# Check the independently curated archive bytes and every source/provenance entry.
catalog=Catalog(native.catalog_root,configuration(TARGET_LOCAL/'operator/trust.json'),readonly=True);artifacts=[]
for descriptor in catalog.snapshot():
 artifact=descriptor['digest'];path=catalog.path(artifact);verified=catalog.validator.verify(path,expected_digest=artifact)
 with zipfile.ZipFile(path) as z:
  prefix=verified.manifest['plugin']['id']+'/'
  for filename in ['LICENSE','COPYRIGHT']:assert z.read(prefix+'notices/'+filename)==(ROOT/filename).read_bytes()
  provenance=json.loads(z.read(prefix+'provenance.json'));assert provenance['upstream_commit']==base
  for name,h in provenance['source_files'].items():assert digest(z.read(prefix+name))==h
 artifacts.append(dict(plugin_id=descriptor['plugin_id'],version=descriptor['version'],digest=artifact,license=verified.manifest['plugin']['license'],root_notices_exact=True,provenance_files=len(provenance['source_files'])))
assert len(artifacts)==19
write('artifact-provenance.json',dict(result='passed_current_curated19_archives_source_and_notices',artifacts=artifacts,catalog_source='fresh_target21_independent_curated_catalog',moving_latest_used=False,limits=['Curated archived metadata/source/notices; no new installation, trust approval or commercial relicensing conclusion.']))
f.guard(state)
write('qualification.json',dict(result='passed_current_official_source_and_application_notices_and19archives',utc=datetime.now(timezone.utc).isoformat(),application_image=state['image_id'],inventory_digest=runtime['inventory_digest'],upstream_commit=base,official_source='official-source.json',application_notice_bundle='notice-bundle.json',curated_artifacts='artifact-provenance.json',python_distributions=len(actual),OS_packages=len(index['os_packages']),native_addons=len(index['native']),deployment_mutations=0,images_built=0,limits=['Static provenance/notice preservation subset only; not full OPS03 or G7/security/license compatibility opinion.','Support-image/worker notice bundles, vendored components, advisory/risk/network/history/layer/secret/reprobuild/release-kit qualification still require their own current evidence.']))
print(json.dumps(dict(result='passed_current_source_notice_subset',official_files=len(names)-len(differences),patched_files=len(patches),Python=len(actual),OS=len(index['os_packages']),archives=19)))
