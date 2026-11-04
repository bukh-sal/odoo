"""Bind the exact upstream2.10 release notice without substituting an Alpine recipe."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-source-notices-01'
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=25) as response:
        raw=response.read(2*1024*1024+1)
    assert len(raw)<=2*1024*1024
    return raw
refurl='https://api.github.com/repos/libexpat/libexpat/git/ref/tags/R_2_10_0'
refraw=fetch(refurl);ref=json.loads(refraw);obj=ref['object'];chain=[dict(url=refurl,sha256=hashlib.sha256(refraw).hexdigest())]
(PRIVATE/'expat-release-ref.json').write_bytes(refraw)
if obj['type']=='tag':
    url=obj['url'];tagraw=fetch(url);tag=json.loads(tagraw)
    (PRIVATE/'expat-release-tag.json').write_bytes(tagraw);chain.append(dict(url=url,sha256=hashlib.sha256(tagraw).hexdigest()));obj=tag['object']
assert obj['type']=='commit';commit=obj['sha']
changesurl=f'https://raw.githubusercontent.com/libexpat/libexpat/{commit}/expat/Changes'
changes=fetch(changesurl);prior=(ROOT/'.local/g7-native-libraries-01/expat210-primary.raw').read_bytes()
assert changes==prior,'Resolved release differs from the retained primary vendor record; inspect before proceeding'
url=f'https://raw.githubusercontent.com/libexpat/libexpat/{commit}/expat/COPYING';raw=fetch(url)
assert b'MIT License' in raw or b'Permission is hereby granted' in raw
digest=hashlib.sha256(raw).hexdigest();path=ROOT/'third_party/alpine-notices/texts'/(digest+'.txt')
if path.exists():assert path.read_bytes()==raw
else:path.write_bytes(raw)
record=dict(result='passed_expat_2_10_upstream_notice_at_exact_release_commit',origin='expat',upstream_release='2.10.0',
    upstream_commit=commit,release_resolution=chain,changes_url=changesurl,changes_sha256=hashlib.sha256(changes).hexdigest(),
    retained_primary_vendor_changes_exact=True,notice=dict(url=url,bytes=len(raw),sha256=digest,path=path.relative_to(ROOT).as_posix()),
    installed_Alpine_version='2.10.0-r0',Alpine_recipe_substituted=False,
    unresolved_recipe_transport='Exact package source_commit remains preserved as declared in the signed APK. Its GitHub mirror path404 and canonical Alpine endpoints418/403 are retained; this upstream notice does not claim the unavailable packaging recipe was reproduced.',
    limits=['Copyright/license text and source origin for the exact upstream release only; no fabricated Alpine recipe or updated package/source hashes.'])
with (OUT/'expat-upstream-notice.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],upstream_commit=commit,notice_bytes=len(raw))))
