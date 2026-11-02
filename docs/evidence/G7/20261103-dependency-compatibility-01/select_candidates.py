"""Select concrete public registry candidates for an isolated compatibility experiment."""
import concurrent.futures,hashlib,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from packaging.specifiers import SpecifierSet
from packaging.utils import parse_wheel_filename
from packaging.version import Version
from modular_platform.operator_os import protect_directory
PRIVATE=ROOT/'.local/g7-dependency-compatibility-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
index=json.loads((ROOT/'docs/evidence/G7/20261102-current-advisories-01/triage-index.json').read_text())
names=sorted({('pypdf' if p['package']=='pypdf2' else p['package']) for p in index['packages']})
runtime=json.loads((ROOT/'.local/g7-current-provenance-01/runtime-observation.json').read_text());tags=set(runtime['accepted_wheel_tags']);python=Version(runtime['python'])
def one(name):
 with urllib.request.urlopen('https://pypi.org/pypi/'+name+'/json',timeout=30) as response:raw=response.read()
 (PRIVATE/(name+'-project.json')).write_bytes(raw);project=json.loads(raw);version=project['info']['version'];assert not Version(version).is_prerelease
 with urllib.request.urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=30) as response:detail=response.read()
 (PRIVATE/(name+'-'+version+'.json')).write_bytes(detail);data=json.loads(detail);required=data['info'].get('requires_python') or ''
 assert python in SpecifierSet(required),name+' latest stable requires incompatible Python; inspect a compatible maintained branch'
 wheels=[];sources=[]
 for f in data['urls']:
  if f.get('yanked'):continue
  if f.get('requires_python') and python not in SpecifierSet(f['requires_python']):continue
  if f['packagetype']=='bdist_wheel':
   _,v,_,wheel_tags=parse_wheel_filename(f['filename'])
   if not {str(t) for t in wheel_tags}&tags:continue
   wheels.append({k:f[k] for k in ['filename','url','digests','size','upload_time_iso_8601']})
  elif f['packagetype']=='sdist':sources.append({k:f[k] for k in ['filename','url','digests','size','upload_time_iso_8601']})
 assert wheels or sources,name+' has no compatible distribution'
 return dict(package=name,version=version,requires_python=required,requires_dist=data['info'].get('requires_dist') or [],license_expression=data['info'].get('license_expression'),license_field=data['info'].get('license'),project_urls=data['info'].get('project_urls'),compatible_wheels=wheels,source_archives=sources,source_build_required=not bool(wheels),metadata_sha256=hashlib.sha256(detail).hexdigest(),source='https://pypi.org/pypi/'+name+'/'+version+'/json')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,names))
queries=dict(queries=[dict(package=dict(ecosystem='PyPI',name=p['package']),version=p['version']) for p in results])
request=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps(queries).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=45) as response:raw=response.read()
(PRIVATE/'candidate-advisories.json').write_bytes(raw);advisories=json.loads(raw);assert len(advisories['results'])==len(results)
for p,r in zip(results,advisories['results']):p['current_advisory_ids']=[v['id'] for v in r.get('vulns',[])];assert not r.get('next_page_token')
value=dict(result='registry_candidates_for_compatibility_probe_not_approved_release',utc=datetime.now(timezone.utc).isoformat(),base_image='sha256:31a673ebbc53fbdecbc5cbfdb5f0eac30d11367630da306d47b5e14cfce17345',Python=str(python),candidates=results,renamed_dependency=dict(previous='PyPDF2',candidate='pypdf',existing_native_adapter='odoo/tools/pdf/_pypdf.py'),limits=['Exact stable registry candidates only; no lock/source/library/runtime mutation performed.','Newer versions are not assumed ABI/API compatible. Native import/image/PDF/HTML/HTTP/token and later full native/lifecycle/performance tests required.','Source-build packages require a separate controlled authorized builder; never execute build backends in pure planning.','A registry no-match is not a full security signoff; OS/vendor/vendored and reachability checks remain.'])
path=OUT/'candidate-selection.json';assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=value['result'],candidates=len(results),source_build_required=[p['package'] for p in results if p['source_build_required']],candidates_with_advisory_matches=[p['package'] for p in results if p['current_advisory_ids']])))
