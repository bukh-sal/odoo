"""Read actual verified catalog members, served static assets and current log streams."""
import base64,hashlib,json,re,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-privacy-delta-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261104-native-uninstall-recovery-01')]
import probe as p
from secret_scan import Scanner
from modular_platform.catalog import Catalog
values={k:base64.b64decode(v) for k,v in json.loads((ROOT/'.local/g7-core23-secret-delta-01/known-values.json').read_bytes()).items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
p.f.OUTPUT=OUT
state,native=p.context();assert native.config['generation']==8
before=p.snapshot(state,'release-secret-delta-before');identity=p.worker(native,'release-secret-delta-worker-before')
assert len(before['mp_example_note'])==2 and len(before['mp_job'])==2
findings=[];packages=[];entries=0
catalog=Catalog(native.catalog_root,native.validator,readonly=True)
for descriptor in catalog.snapshot():
 digest=descriptor['digest'];path=catalog.path(digest);verified=catalog.validator.verify(path,expected_digest=digest)
 with zipfile.ZipFile(path) as archive:
  for info in archive.infolist():
   if info.is_dir():continue
   raw=archive.read(info);assert len(raw)==info.file_size and len(raw)<=64*1024*1024
   entries+=1;findings+=scanner.inspect_bytes(raw,'curated-package/'+digest+'/'+info.filename)
 packages.append(dict(digest=digest,plugin_id=descriptor['plugin_id'],version=descriptor['version'],entries=len(verified.inventory)))
assert len(packages)>=19
fixture=p.load(p.LOCAL/'fixtures.json');p.r1_probe.r1.r0.LOCAL=p.LOCAL
client=p.r1_probe.Client(state,fixture,'alice')
def fetch(path):
 request=urllib.request.Request(client.base+path,headers={'X-MP-Client-Release':client.release_token,'X-MP-Workspace':fixture['workspaces']['A']['public_id']})
 with client.http.open(request,timeout=30) as response:assert response.code==200;return response.read()
html=fetch('/app/org.example.notes/?workspace='+fixture['workspaces']['A']['public_id'])
urls={v.decode() for v in re.findall(rb'(?:src|href)=[\"\x27]([^\"\x27]*/web/assets/[^\"\x27]+)',html)}
status,dto=client.request('/api/v1/context?plugin_id=org.example.canvas',workspace='A');assert status==200
def visit(value):
 if isinstance(value,dict):
  for v in value.values():visit(v)
 elif isinstance(value,list):
  for v in value:visit(v)
 elif isinstance(value,str) and value.startswith('/') and value.endswith(('.js','.css')):urls.add(value)
visit(dto);assert len(urls)>=2
cache=PRIVATE/'served-assets';cache.mkdir();assets=[];canvas=False
for i,path in enumerate(sorted(urls)):
 raw=fetch(path);(cache/str(i)).write_bytes(raw)
 findings+=scanner.inspect_bytes(raw,'served-static'+path)
 assets.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
 canvas=canvas or (b'org.example.canvas' in raw and b'mp.pages' in raw)
assert canvas
original=p.load(ROOT/'.local/g6-events/operator/target.json')
ids=[native.config['worker_id'],identity['id'],state['project']+'-db-1',state['project']+'-edge-1',original['worker_id'],
 'mp-disposable-document-stats-07-document-stats-1',original['project']+'-db-1',original['project']+'-edge-1']
logcache=PRIVATE/'current-logs';logcache.mkdir();logs=[]
for i,ident in enumerate(ids):
 meta=json.loads(subprocess.check_output(['docker','inspect','--type','container',ident]))[0];assert meta['State']['Running']
 r=subprocess.run(['docker','logs',meta['Id']],capture_output=True,timeout=30);assert r.returncode==0
 raw=r.stdout+b'\n'+r.stderr;path=logcache/str(i);path.write_bytes(raw)
 findings+=scanner.inspect_file(path,'current-container-log/'+meta['Name'])
 logs.append(dict(id=meta['Id'],name=meta['Name'],sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
assert p.snapshot(state,'release-secret-delta-after')==before
assert p.worker(native,'release-secret-delta-worker-after')==identity
p.f.guard(state)
report=dict(result='actual_packages_assets_and_current_logs_scanned_triage_required',image=state['image_id'],configuration_generation=8,
 packages=packages,decompressed_entries=entries,served_assets=assets,Canvas_registration_observed=True,current_container_logs=logs,
 known_values=123,findings=findings,all17tables_worker_original_configs_exact=True,
 limits=['Actual19-or-more curated verified archives/current static JS+CSS/8 running original-and-fresh app-worker-DB-edge log streams. No browser rendering or network trace claim.',
 'Dynamic authenticated bootstrap/CSRF/session responses are legitimate secret-bearing data, kept in memory and excluded from public static assets.',
 'Ordinary Alice login/read only; no plugin lifecycle, worker run, schema/config mutation or container creation. Retained diagnostic streams require separate incremental scan.'])
with (OUT/'packages-assets-logs.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(packages=len(packages),entries=entries,assets=len(assets),logs=len(logs),findings=len(findings))),flush=True)
