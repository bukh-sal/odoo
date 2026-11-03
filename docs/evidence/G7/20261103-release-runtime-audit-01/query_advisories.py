"""Current public name/version advisory queries, including Debian SOURCE packages."""
import hashlib,importlib.metadata,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-runtime-audit-01/advisories'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
def save(path,value):
 assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def norm(name):return re.sub('[-_.]+','-',name).lower()
roles={};inputs=[]
for name,role in [('application-index.json','application'),('worker-index.json','worker')]:
 path=OUT/name;data=json.loads(path.read_text());inputs.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 for p in data['python']:roles.setdefault(('PyPI',norm(p['name']),p['version']),set()).add(role)
 for p in data['os_packages']:
  assert p['source_package'] and p['source_version'];roles.setdefault(('Debian:12',p['source_package'],p['source_version']),set()).add(role+'_OS')
for d in importlib.metadata.distributions():roles.setdefault(('PyPI',norm(d.metadata['Name']),d.version),set()).add('isolated_operator_tooling')
lock=ROOT/'packages/host_sdk/package-lock.json';inputs.append(dict(path=lock.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(lock.read_bytes()).hexdigest()))
for path,p in json.loads(lock.read_text())['packages'].items():
 if path:roles.setdefault(('npm',path.removeprefix('node_modules/'),p['version']),set()).add('locked_host_build_tool_or_optional_variant')
ordered=sorted(roles);queries=[dict(package=dict(ecosystem=e,name=n),version=v) for e,n,v in ordered]
save(OUT/'advisory-query-inputs.json',dict(result='public_name_version_only',queries=queries,roles=[sorted(roles[k]) for k in ordered],inputs=inputs,sources=['https://google.github.io/osv.dev/post-v1-querybatch/','https://security-tracker.debian.org/tracker/'],limits=['No code, credentials, file contents or user records sent.','Debian source packages/versions queried, not binary package names. CPython/vendored libraries/PG/nginx remain additional scope.']))
save(PRIVATE/'state.json',dict(state='querying_current_public_advisories',queries=len(queries),utc=datetime.now(timezone.utc).isoformat()))
results=[{} for q in queries];pending=list(range(len(queries)));pages=[]
for page in range(20):
 if not pending:break
 payload={'queries':[dict(queries[i],**({'page_token':results[i]['next_page_token']} if results[i].get('next_page_token') else {})) for i in pending]}
 request=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','User-Agent':'modular-platform-local-release-audit/1'})
 with urllib.request.urlopen(request,timeout=50) as response:raw=response.read();headers=dict(response.headers)
 (PRIVATE/('page-'+str(page)+'.json')).write_bytes(raw);save(PRIVATE/('page-'+str(page)+'-headers.json'),headers);value=json.loads(raw);assert len(value['results'])==len(pending)
 pages.append(dict(page=page,queries=len(pending),sha256=hashlib.sha256(raw).hexdigest()))
 next_pending=[]
 for i,result in zip(pending,value['results']):
  entries={r['id']:r for r in results[i].get('vulns',[])};entries.update({r['id']:r for r in result.get('vulns',[])})
  results[i]=dict(vulns=list(entries.values()))
  if result.get('next_page_token'):results[i]['next_page_token']=result['next_page_token'];next_pending.append(i)
 pending=next_pending
assert not pending,'Pagination incomplete: preserve exact page tokens; do not call advisory scope complete'
matches=[dict(query=q,roles=sorted(roles[key]),advisories=result.get('vulns',[])) for key,q,result in zip(ordered,queries,results)]
ids=sorted({v['id'] for row in matches for v in row['advisories']})
save(OUT/'advisory-matches.json',dict(result='current_matches_require_review',utc=datetime.now(timezone.utc).isoformat(),source='https://api.osv.dev/v1/querybatch',queries=len(queries),pages=pages,packages_with_matches=sum(bool(r['advisories']) for r in matches),unique_advisories=ids,matches=matches,limits=['Matches are not an exploitability or final security verdict; details/withdrawals/backports/reachability need primary-source review.','OS vendor cross-check, bundled libraries/CPython/PG/nginx and image/history/archive/network/license/secret audit remain.']))
(PRIVATE/'state.json').write_text(json.dumps(dict(state='matches_collected_review_pending',queries=len(queries),unique_advisories=len(ids)),indent=2)+'\n')
summary={role:sum(bool(row['advisories']) for row in matches if role in row['roles']) for role in sorted({r for values in roles.values() for r in values})}
print(json.dumps(dict(result='current_matches_collected_review_pending',queries=len(queries),unique_advisories=len(ids),matched_package_versions_by_role=summary)))
