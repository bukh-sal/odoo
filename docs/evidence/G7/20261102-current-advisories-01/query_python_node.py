"""Current public advisory lookup for installed Python/locked host Node versions."""
import hashlib,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PRIVATE=ROOT/'.local/g7-current-advisories-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
def save(path,value):assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def norm(value):return re.sub('[-_.]+','-',value).lower()
rows={};inputs=[]
for name,role in [('runtime-license-index.json','application'),('worker-runtime-license-index.json','independent_worker')]:
 path=OUT.parent/'20261102-current-provenance-01'/name;source=json.loads(path.read_text());inputs.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 for p in source['python']:
  key=('PyPI',norm(p['name']),p['version']);rows.setdefault(key,set()).add(role)
lock=ROOT/'packages/host_sdk/package-lock.json';inputs.append(dict(path=str(lock.relative_to(ROOT)),sha256=hashlib.sha256(lock.read_bytes()).hexdigest()))
for path,p in json.loads(lock.read_text())['packages'].items():
 if path:rows.setdefault(('npm',path.removeprefix('node_modules/'),p['version']),set()).add('host_typecheck_tool')
ordered=sorted(rows);queries=[dict(package=dict(ecosystem=e,name=n),version=v) for e,n,v in ordered]
save(OUT/'python-node-query-inputs.json',dict(result='public_package_version_queries_only',queries=queries,roles=[sorted(rows[k]) for k in ordered],inputs=inputs,protocol_documentation='https://google.github.io/osv.dev/post-v1-querybatch/'))
save(PRIVATE/'state.json',dict(state='querying_public_OSV',queries=len(queries),utc=datetime.now(timezone.utc).isoformat()))
request=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps(dict(queries=queries)).encode(),headers={'Content-Type':'application/json','User-Agent':'modular-platform-local-release-audit/1'})
with urllib.request.urlopen(request,timeout=45) as response:
 raw=response.read();headers=dict(response.headers)
save(PRIVATE/'batch-http-headers.json',headers);(PRIVATE/'python-node-batch-response.json').write_bytes(raw)
result=json.loads(raw);assert len(result['results'])==len(queries) and all(not r.get('next_page_token') for r in result['results']),'Pending pagination requires a separate recorded continuation; do not mark complete'
matches=[dict(query=q,roles=sorted(rows[key]),advisories=r.get('vulns',[])) for key,q,r in zip(ordered,queries,result['results'])]
unique=sorted({v['id'] for r in matches for v in r['advisories']})
save(OUT/'python-node-advisory-matches.json',dict(result='queried_matches_require_review',utc=datetime.now(timezone.utc).isoformat(),source='https://api.osv.dev/v1/querybatch',response_sha256=hashlib.sha256(raw).hexdigest(),queries=len(queries),packages_with_matches=sum(bool(r['advisories']) for r in matches),unique_advisories=unique,matches=matches,limits=['Public advisory matching only, not a security pass or exploitability judgment.','Names/versions only sent; no source, credentials, workspace records or user documents.','OS/vendor runtimes, vendored libraries, archive/layer/history secrets, network and actual fresh release tests remain separate.']))
(PRIVATE/'state.json').write_text(json.dumps(dict(state='python_node_matches_collected_review_pending',queries=len(queries),unique_advisories=unique),indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result='advisory_matches_collected_review_pending',queries=len(queries),packages_with_matches=sum(bool(r['advisories']) for r in matches),unique_advisories=len(unique))))
