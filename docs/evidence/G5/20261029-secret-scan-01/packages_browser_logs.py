"""Read-only decompressed release packages, actual browser assets and scoped logs."""
from datetime import datetime,timezone
import hashlib,importlib.util,json,re,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(OUTPUT)]
from tree import context
from secret_scan import save_report
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog

def main():
 dest=OUTPUT/'packages-browser-logs.json';assert not dest.exists();scanner=context();started=time.monotonic();findings=[];packages={};entries=0;expanded=0
 for catalog,trust in [('.local/operator/catalog','.local/operator/trust.json'),('.local/g5-lifecycle/operator/permission-upgrade/catalog','.local/g5-lifecycle/operator/permission-upgrade/trust.json')]:
  t=json.loads((ROOT/trust).read_text());validator=ArtifactValidator(TrustPolicy(mode=t['mode'],approved_digests=frozenset(t['approved_digests']),generation=t['generation']));cat=Catalog(ROOT/catalog,validator,readonly=True)
  for descriptor in cat.snapshot():
   path=cat.path(descriptor['digest']);packages.setdefault(descriptor['digest'],dict(path=path,locations=[]))['locations'].append(catalog)
 inventory=json.loads((LOCAL/'image-inventory.json').read_text())
 for name,item in inventory.items():
  if item['location'].endswith('.mplug'):
   digest='sha256:'+item['sha256'];packages.setdefault(digest,dict(path=LOCAL/'image-files'/name,locations=[]))['locations'].append(item['location'])
 package_records=[]
 for digest,item in packages.items():
  # All bytes must pass the strict existing bounded data-only ZIP validator.
  verified=ArtifactValidator(TrustPolicy(approved_digests=frozenset([digest]))).verify(item['path'],expected_digest=digest)
  with zipfile.ZipFile(item['path']) as archive:
   for info in archive.infolist():
    if info.is_dir():continue
    data=archive.read(info);assert len(data)==info.file_size and len(data)<=64*1024*1024;entries+=1;expanded+=len(data);findings+=scanner.inspect_bytes(data,'package/'+digest+'/'+info.filename)
  package_records.append(dict(digest=digest,locations=item['locations'],plugin=verified.manifest['plugin'],entries=len(verified.inventory),expanded=verified.expanded_size))
 print(json.dumps(dict(state='packages_scanned',archives=len(packages),entries=entries)),flush=True)
 # Authentication is private; only static content is a release bundle. Dynamic
 # bootstrap/session responses legitimately contain per-session CSRF values.
 spec=importlib.util.spec_from_file_location('http_security_probe',OUTPUT.parent/'20261029-http-security-02/probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 state=json.loads((ROOT/'.local/g5-httpsecurity/state.json').read_text());fixture=json.loads((ROOT/'.local/g5-httpsecurity/fixtures.json').read_text());client=m.Client('production');client.login(state,fixture,'alice')
 qualification=json.loads((OUTPUT.parent/'20261029-http-security-02/HTTP-qualification.json').read_text());assets={a['path']:a for c in qualification['checks'] for a in c.get('assets',[])};browser=[];canvas_in_bundle=False
 for path,expected in assets.items():
  code,_,headers,data=client.request(path);assert code==200 and hashlib.sha256(data).hexdigest()==expected['sha256'];canvas_in_bundle=canvas_in_bundle or (b'org.example.canvas' in data and b'mp.pages' in data);findings+=scanner.inspect_bytes(data,'served-browser'+path);browser.append(dict(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 # The optional module URL comes from the authenticated frozen context DTO.
 wid=fixture['workspaces']['A']['public_id'];code,context_dto,_,_=client.request('/api/v1/context?plugin_id=org.example.canvas',headers={'X-MP-Client-Release':client.release,'X-MP-Workspace':wid});assert code==200
 (LOCAL/'browser-context.json').write_text(json.dumps(context_dto),encoding='utf8')
 # Traverse public DTO URLs, without serializing actor/session state to evidence.
 urls=set()
 def visit(value):
  if isinstance(value,dict):
   for v in value.values():visit(v)
  elif isinstance(value,list):
   for v in value:visit(v)
  elif isinstance(value,str) and value.startswith('/') and (value.endswith('.js') or value.endswith('.css')):urls.add(value)
 visit(context_dto)
 for path in sorted(urls):
  code,_,headers,data=client.request(path,headers={'X-MP-Client-Release':client.release,'X-MP-Workspace':wid});assert code==200;canvas_in_bundle=canvas_in_bundle or (b'org.example.canvas' in data and b'mp.pages' in data);findings+=scanner.inspect_bytes(data,'served-browser'+path);browser.append(dict(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 assert len(browser)>=2 and canvas_in_bundle,'Canvas registration not observed in regular native bundle';browser.append(dict(capability='optional Canvas custom page registered within native assets',bundled=True))
 print(json.dumps(dict(state='browser_scanned',assets=len(browser))),flush=True)
 scope=json.loads((LOCAL/'scope.json').read_text());paths=[ROOT/p for p in scope['private_logs'] if (ROOT/p).is_file()];findings+=scanner.scan_paths(paths,LOCAL/'patterns-v2.regex',root=ROOT)
 # Include running and retained stopped app/edge/native-test container streams,
 # scoped to exact project identities discovered from owned fixture state.
 rows=[json.loads(x) for x in subprocess.check_output(['docker','ps','-a','--format','{{json .}}']).splitlines()];containers=[];cache=LOCAL/'container-logs';cache.mkdir()
 for row in rows:
  labels=dict(v.split('=',1) for v in row['Labels'].split(',') if '=' in v);project=labels.get('com.docker.compose.project');name=row['Names']
  if project not in scope['projects'] and not any(name.startswith(p+'-') for p in scope['projects']):continue
  if project not in scope['projects']:project=next(p for p in scope['projects'] if name.startswith(p+'-'))
  result=subprocess.run(['docker','logs',row['ID']],capture_output=True,timeout=60)
  assert result.returncode==0,'Container log read failed; no silent scope exclusion'
  data=result.stdout+b'\n'+result.stderr;path=cache/row['ID'];path.write_bytes(data);fs=scanner.inspect_file(path,'container-log/'+name);findings+=fs;containers.append(dict(id=row['ID'],name=name,project=project,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 print(json.dumps(dict(state='logs_scanned',private_files=len(paths),containers=len(containers))),flush=True)
 report=dict(result='scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),packages=package_records,expanded_entries=entries,expanded_bytes=expanded,browser_assets=browser,private_log_files=len(paths),private_log_bytes=sum(p.stat().st_size for p in paths),container_logs=containers,elapsed_seconds=round(time.monotonic()-started,3),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,limits=['Explicit private credential/config/DB dumps/checkpoints are secret stores, not public deliverables; log files are still scanned.','Read-only owned container logs include retained native-test containers; unrelated Docker projects excluded.','Actual static browser assets scanned; authenticated dynamic bootstrap contains legitimate CSRF and is not a static browser bundle.','No archive-selected extraction path, code import or artifact execution.'])
 save_report(dest,report);print(json.dumps({k:report[k] for k in ['result','expanded_entries','private_log_files','elapsed_seconds','known_secret_findings','generic_findings']}),flush=True)
if __name__=='__main__':main()
