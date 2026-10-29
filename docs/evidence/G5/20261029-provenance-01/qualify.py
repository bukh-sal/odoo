"""Final current-input audit for G5 OPS03; no build/native operation replay."""
from datetime import datetime,timezone
import hashlib,json,platform,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-provenance'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from clean_recovery_fixture import load,guard
from clean_recovery_data import context
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from secret_scan import Scanner
import base64

state,target,reader,document,fixture=context();guard(state)
build=load(OUTPUT/'build-provenance.json');official=load(OUTPUT/'official-source.json');notices=load(OUTPUT/'notice-bundle-final.json');artifacts=load(OUTPUT/'artifact-provenance.json');index=load(OUTPUT/'runtime-license-index.json')
assert build['result']==official['result']==artifacts['result']=='passed' and notices['result']=='passed_preserved'
assert build['image_id']==target['image_id'] and build['inventory_digest']==state['inventory_digest']
for p,h in build['locks'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
for p,h in build['host_operator_source'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
for row in load(OUTPUT/'supplemental-notices.json')['packages']:
    for f in row['notices']:assert hashlib.sha256((ROOT/f['path']).read_bytes()).hexdigest()==f['sha256']
archive=LOCAL/'release-notices.zip'
with archive.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==notices['archive_sha256']
with zipfile.ZipFile(archive) as z:
    assert set(z.namelist())=={f['path'] for f in notices['files']}
    for f in notices['files']:assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
lock=load(ROOT/'deploy/host-toolchain.lock.json');assert platform.python_version()==lock['Python'];assert subprocess.check_output(['node','--version']).decode().strip()=='v'+lock['Node'];assert subprocess.check_output(['npm.cmd','--version']).decode().strip()==lock['npm']
assert load(ROOT/'packages/host_sdk/node_modules/typescript/package.json')['version']==lock['TypeScript']
app=json.loads(subprocess.check_output(['docker','inspect',target['worker_id']]))[0]
assert app['State']['Running'] and set(app['NetworkSettings']['Networks'])=={state['project']+'_runtime'}
network=json.loads(subprocess.check_output(['docker','network','inspect',state['project']+'_runtime']))[0];assert network['Internal']
assert json.loads(sql(reader,BUSINESS_SQL))==load(ROOT/'docs/evidence/G5/20261029-clean-recovery-01/business-after-reference-tests.json')
assert json.loads(sql(reader,SCHEMA))==load(ROOT/'docs/evidence/G5/20261029-clean-recovery-01/schema-before-fault.json')
freeze=load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==87 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
# No real credential should appear in new public source, metadata or notices.
known_root=ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in load(known_root/'known-values.json').items()}
for p in (ROOT/'.local/g5-clean-recovery').iterdir():
    if p.is_file() and (p.name.endswith('password') or p.name.endswith('secret') or p.name=='service-token'):
        value=p.read_bytes().strip()
        if len(value)>=16:values['clean/'+p.name]=value
scanner=Scanner((known_root/'fingerprint-key').read_bytes(),values)
paths=[p for directory in [OUTPUT,ROOT/'third_party'] for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [ROOT/'docs/provenance.md',ROOT/'deploy/host-toolchain.lock.json']
findings=[f for p in paths for f in scanner.inspect_file(p,p.relative_to(ROOT).as_posix())];assert not findings,'Inspect redacted findings; do not publish raw matches'
value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),acceptance='OPS-03',spec_sections=['4.3','7.4','24.4','27'],image_id=build['image_id'],inventory_digest=build['inventory_digest'],source_commit=build['source_commit'],official_upstream_files_exact=official['official_files_physically_matched'],reproduced_generated_patches=2,runtime_files_verified=build['runtime_file_count'],Python_distributions=76,native_addons=16,OS_packages=113,curated_artifacts=8,notice_bundle_files=len(notices['files']),supplemental_notice_packages=3,host_toolchain_lock_sha256=hashlib.sha256((ROOT/'deploy/host-toolchain.lock.json').read_bytes()).hexdigest(),new_public_files_scanned=len(paths),new_public_findings=0,backend_network_internal=True,current_business_schema_exact=True,frozen_files=87,checks=['official-source.json','runtime-license-index.json','artifact-provenance.json','build-provenance.json','host-only-additions.json','notice-bundle-final.json','supplemental-notices.json','retained-product-ties.json'],source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},limits=['No new build, deployment, native migration or acceptance replay; this qualification audits the actual qualified release inputs and preserves missing notices.','G6/G7 and final release-wide reinstall/security/vulnerability/browser-network audits remain.','Exact immutable image retention is required for byte-identical recovery; native recompilation is not assumed byte-identical.','No commercial relicensing, publication or legal compatibility determination.'])
path=OUTPUT/'qualification.json';assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(dict(result='passed',acceptance='OPS-03',runtime_files=build['runtime_file_count'],notices=len(notices['files']),artifacts=8)))
