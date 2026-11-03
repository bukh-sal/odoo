"""Retain exact public vendor advisory inputs, no project contents sent."""
import concurrent.futures,hashlib,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-support-images-02/vendor'
PRIVATE.mkdir()
sources={'openssl4':'https://openssl-library.org/news/vulnerabilities-4.0/index.html','openssl3':'https://openssl-library.org/news/vulnerabilities-3.0/index.html','openssl35':'https://openssl-library.org/news/vulnerabilities-3.5/index.html','postgres':'https://www.postgresql.org/support/security/','nginx':'https://nginx.org/en/security_advisories.html','alpine-main':'https://secdb.alpinelinux.org/v3.24/main.json','alpine-community':'https://secdb.alpinelinux.org/v3.24/community.json'}
def fetch(item):
 name,url=item
 request=urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-release-audit/1'})
 with urllib.request.urlopen(request,timeout=45) as response:raw=response.read();headers=dict(response.headers)
 (PRIVATE/(name+'.raw')).write_bytes(raw);(PRIVATE/(name+'-headers.json')).write_text(json.dumps(headers,indent=2))
 return dict(name=name,url=url,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),content_type=headers.get('Content-Type'),private_input=str((PRIVATE/(name+'.raw')).relative_to(ROOT)))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch,sources.items()))
with (OUT/'vendor-snapshots.json').open('x',encoding='utf8') as f:json.dump(dict(result='primary_vendor_inputs_retained',utc=datetime.now(timezone.utc).isoformat(),sources=rows,limits=['Collection only; ranges/backports/reachability need comparison with exact installed identities.']),f,indent=2)
print(json.dumps([dict(name=r['name'],bytes=r['bytes']) for r in rows]))
