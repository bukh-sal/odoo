"""Retain Debian's primary tracker and select actual matched source-package rows."""
import hashlib,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-runtime-audit-01/advisories'
path=PRIVATE/'debian-tracker.json';assert not path.exists()
url='https://security-tracker.debian.org/tracker/data/json';request=urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-release-audit/1'})
with urllib.request.urlopen(request,timeout=50) as response:raw=response.read(100*1024*1024+1);headers=dict(response.headers)
assert len(raw)<=100*1024*1024;data=json.loads(raw);path.write_bytes(raw)
(PRIVATE/'debian-tracker-headers.json').write_text(json.dumps(headers,indent=2)+'\n')
matches=json.loads((OUT/'advisory-matches.json').read_text());packages={r['query']['package']['name'] for r in matches['matches'] if r['advisories'] and r['query']['package']['ecosystem']=='Debian:12'}
selected={name:data.get(name) for name in sorted(packages)}
assert all(v is not None for v in selected.values())
record=dict(result='primary_Debian_tracker_retained_review_pending',utc=datetime.now(timezone.utc).isoformat(),source=url,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),matched_source_packages=len(packages),selected=selected,limits=['Bookworm source-package fix/status/urgency/nodsa data retained; version comparison/record alias matching/reachability interpretation remains.','Current tracker snapshot, not an assertion that every match is exploitable or automatically acceptable.'])
with (OUT/'debian-source-tracker.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],bytes=len(raw),packages=len(packages))))
