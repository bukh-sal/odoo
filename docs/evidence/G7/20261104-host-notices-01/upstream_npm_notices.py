"""Preserve furnished root license/attribution at each registry-pinned source commit."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import urllib.parse

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-host-notices-01/upstream-notices'
assert not PRIVATE.exists();PRIVATE.mkdir()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=30) as response:raw=response.read(2*1024*1024+1)
    assert len(raw)<=2*1024*1024
    return raw
records=json.loads((OUT/'npm-supplement-artifacts.json').read_text())['records'];rows=[]
for record in records:
    url=record['repository']['url'].removeprefix('git+').removesuffix('.git');parts=urllib.parse.urlsplit(url)
    assert parts.scheme=='https' and parts.hostname=='github.com'
    repository=parts.path.strip('/');assert re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
    commit=record['gitHead'];assert re.fullmatch('[0-9a-f]{40}',commit)
    api=f'https://api.github.com/repos/{repository}/contents?ref={commit}'
    raw=fetch(api);listing=json.loads(raw);safe=record['name'].replace('@','').replace('/','--')
    (PRIVATE/(safe+'-listing.json')).write_bytes(raw);notices=[]
    for item in listing:
        if item['type']!='file' or not re.match(r'(?i)^(?:licen[cs]e|copying|copyright|notice|readme)(?:$|[._-])',item['name']):continue
        notice_url=f'https://raw.githubusercontent.com/{repository}/{commit}/'+urllib.parse.quote(item['path'],safe='/')
        value=fetch(notice_url);path=PRIVATE/(safe+'--'+item['name']);assert not path.exists();path.write_bytes(value)
        notices.append(dict(source_path=item['path'],url=notice_url,sha256=sha(value),bytes=len(value),private_file=path.relative_to(ROOT).as_posix()))
    assert notices
    rows.append(dict(name=record['name'],version=record['version'],declared_license=record['license'],
        repository=url,source_commit=commit,registry_artifact_binding=record['tarball_sha512'],listing_url=api,
        listing_sha256=sha(raw),notices=notices,standalone_license_found=any(re.match('(?i)^licen[cs]e',p['source_path']) for p in notices)))
result=dict(result='exact_source_commit_npm_notices_preserved',records=rows,source_executed=False,
    limits=['Preserves furnished source license/README attribution and raw package declarations without inventing a permission statement.',
            'Missing standalone source license files remain explicit for final disposition; no commercial compatibility opinion.'])
with (OUT/'npm-upstream-notices.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],packages=len(rows),with_standalone_license=sum(p['standalone_license_found'] for p in rows))))
