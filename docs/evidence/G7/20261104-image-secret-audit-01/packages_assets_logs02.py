"""Scan bounded verified packages, served static bundles, and exact owned logs."""
import base64,hashlib,json,re,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker,LOCAL
from modular_platform.catalog import Catalog
from secret_scan import Scanner,save_report
import r1_probe
values={k:base64.b64decode(v) for k,v in json.loads((PRIVATE/'known-values.json').read_bytes()).items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==5
before=snapshot(state,'asset-secret02-before');identity=worker(native,'asset-secret02-worker-before')
findings=[];packages=[];entries=0
catalog=Catalog(native.catalog_root,native.validator,readonly=True)
for descriptor in catalog.snapshot():
 digest=descriptor['digest'];path=catalog.path(digest);verified=catalog.validator.verify(path,expected_digest=digest)
 with zipfile.ZipFile(path) as archive:
  for info in archive.infolist():
   if info.is_dir():continue
   data=archive.read(info);assert len(data)==info.file_size and len(data)<=64*1024*1024
   entries+=1;findings+=scanner.inspect_bytes(data,'package/'+digest+'/'+info.filename)
 packages.append(dict(digest=digest,plugin_id=descriptor['plugin_id'],version=descriptor['version'],entries=len(verified.inventory)))
assert len(packages)==19
print(json.dumps(dict(state='curated_packages_scanned',archives=len(packages),entries=entries)),flush=True)
fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'alice')
def fetch(path):
 request=urllib.request.Request(client.base+path,headers={'X-MP-Client-Release':client.release_token,'X-MP-Workspace':fixture['workspaces']['A']['public_id']})
 with client.http.open(request,timeout=30) as response:assert response.code==200;return response.read()
html=fetch('/app/org.example.notes/?workspace='+fixture['workspaces']['A']['public_id']);urls={p.decode() for p in re.findall(rb'(?:src|href)=[\"\x27]([^\"\x27]*/web/assets/[^\"\x27]+)',html)}
status,dto=client.request('/api/v1/context?plugin_id=org.example.canvas',workspace='A');assert status==200
def visit(value):
 if isinstance(value,dict):
  for v in value.values():visit(v)
 elif isinstance(value,list):
  for v in value:visit(v)
 elif isinstance(value,str) and value.startswith('/') and value.endswith(('.js','.css')):urls.add(value)
visit(dto);assert len(urls)>=2
cache=PRIVATE/'served-assets';cache.mkdir();assets=[];canvas=False
for index,path in enumerate(sorted(urls)):
 raw=fetch(path);(cache/str(index)).write_bytes(raw);findings+=scanner.inspect_bytes(raw,'served-static'+path)
 assets.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
 canvas=canvas or (b'org.example.canvas' in raw and b'mp.pages' in raw)
assert canvas
print(json.dumps(dict(state='actual_assets_scanned',assets=len(assets))),flush=True)
logcache=PRIVATE/'current-container-logs';logcache.mkdir();logs=[]
original=f.load(ROOT/'.local/g6-events/state.json')
ids=[native.config['worker_id'],identity['id'],state['project']+'-edge-1',state['project']+'-db-1',original['project']+'-edge-1',original['project']+'-db-1']
original_target=f.load(ROOT/'.local/g6-events/operator/target.json');ids.append(original_target['worker_id'])
ids.append('mp-disposable-document-stats-07-document-stats-1')
for index,ident in enumerate(ids):
 info=json.loads(subprocess.check_output(['docker','inspect',ident]))[0];assert info['State']['Running']
 r=subprocess.run(['docker','logs',info['Id']],capture_output=True,timeout=30);assert r.returncode==0
 raw=r.stdout+b'\n'+r.stderr;path=logcache/str(index);path.write_bytes(raw)
 findings+=scanner.inspect_file(path,'container-log/'+info['Name'].lstrip('/'))
 logs.append(dict(id=info['Id'],name=info['Name'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
assert snapshot(state,'asset-secret02-after')==before and worker(native,'asset-secret02-worker-after')==identity;f.guard(state)
save_report(OUT/'packages-assets-current-logs.json',dict(result='scanned_triage_required',image_id=state['image_id'],packages=packages,expanded_entries=entries,served_assets=assets,Canvas_registration_observed=True,current_container_logs=logs,known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,all17tables_worker_original_configs_exact=True,limits=['Actual current original+fresh app/worker/DB/edge container streams; retained executor/private diagnostic logs require separate audit.','Static JS/CSS only; per-session dynamic bootstrap/CSRF responses are legitimate secret-bearing authentication data and excluded from release assets.','Curated19 archive bytes strictly verified and decompressed, no archive-selected extraction or code import.']))
print(json.dumps(dict(state='packages_assets_current_logs_scanned',known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings))),flush=True)

