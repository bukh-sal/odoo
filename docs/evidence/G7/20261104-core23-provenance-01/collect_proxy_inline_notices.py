"""Preserve checksummed source attribution for packages without standalone notices."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import tarfile
import urllib.request
import urllib.error
import urllib.parse

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-source-notices-01'
blobs=ROOT/'third_party/alpine-notices/texts';inputs=PRIVATE/'inline-sources';assert not inputs.exists();inputs.mkdir()
recipes=json.loads((OUT/'proxy-source-recipes.json').read_text())['records']
def sha(raw):return hashlib.sha256(raw).hexdigest()
def preserve(origin,member,raw,source):
    digest=sha(raw);path=blobs/(digest+'.txt')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    return dict(origin=origin,member=member,bytes=len(raw),sha256=digest,path=path.relative_to(ROOT).as_posix(),source=source)
jobs=[];records=[];notices=[]
for row in recipes:
    if row['origin'] not in {'alpine-base','alpine-baselayout','alpine-keys'}:continue
    recipe=(ROOT/row['private_file']).read_bytes();assert sha(recipe)==row['sha256']
    checksums=re.findall(r'^([0-9a-f]{128})  ([^\r\n]+)$',recipe.decode(),re.M)
    for digest,name in checksums:
        assert PurePosixPath(name).name==name and '..' not in name
        if name.startswith(('protocols-','services-')):
            url='https://distfiles.alpinelinux.org/distfiles/v3.24/'+urllib.parse.quote(name,safe='')
        else:url=row['url'].rsplit('/',1)[0]+'/'+urllib.parse.quote(name,safe='')
        jobs.append((row['origin'],name,digest,url))
    records.append(dict(origin=row['origin'],recipe_url=row['url'],recipe_sha256=row['sha256'],
        source_commit=row['source_commit'],declared_license=row['declared']['license'],declared_source_files=len(checksums),
        result='source_files_pending' if checksums else 'recipe_contains_generated_release_metadata_only',
        note='No synthetic upstream license or permission statement is created. Preserve actual declared license and all furnished attribution.'))
def fetch(job):
    origin,name,expected,url=job
    try:
        with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(2*1024*1024+1)
        assert len(raw)<=2*1024*1024 and hashlib.sha512(raw).hexdigest()==expected
        path=inputs/(origin+'--'+name);assert not path.exists();path.write_bytes(raw)
        return dict(origin=origin,name=name,url=url,source_sha512=expected,sha256=sha(raw),bytes=len(raw),
                    private_file=path.relative_to(ROOT).as_posix(),result='verified_source_file',
                    has_attribution=bool(re.search(rb'copyright|licen[cs]e|SPDX-',raw,re.I)))
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,AssertionError) as error:
        return dict(origin=origin,name=name,url=url,result='source_file_unavailable_or_unverified',error=type(error).__name__,status=getattr(error,'code',None))
with ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(fetch,jobs))
for row in files:
    if row['result']=='verified_source_file' and row['has_attribution']:
        raw=(ROOT/row['private_file']).read_bytes();notices.append(preserve(row['origin'],row['name'],raw,dict(url=row['url'],sha512=row['source_sha512'])))
for row in records:
    subset=[item for item in files if item['origin']==row['origin']]
    if subset:row['result']='declared_source_files_verified' if all(item['result']=='verified_source_file' for item in subset) else 'source_file_review_pending'
ca=next(row for row in json.loads((OUT/'proxy-source-notices.json').read_text())['records'] if row['origin']=='ca-certificates')
archive=ROOT/ca['private_archive']
with archive.open('rb') as stream:assert hashlib.file_digest(stream,'sha512').hexdigest()==ca['source_sha512']
with tarfile.open(archive) as t:
    for member in t:
        if not member.isfile() or member.size>2*1024*1024:continue
        raw=t.extractfile(member).read()
        if re.search(rb'copyright|licen[cs]e|SPDX-',raw,re.I):
            notices.append(preserve('ca-certificates',member.name,raw,dict(archive=ca['source_archive'],sha512=ca['source_sha512'])))
report=dict(result='inline_source_notice_collection_complete_pending_coverage_review',origins=records,source_files=files,
    preserved_inline_attribution_sources=notices,source_or_recipe_executed=False,
    limits=['Full furnished source files with embedded attribution are preserved as opaque text, not executed or installed.',
            'The base release package generates version/issue metadata from its recipe; keys carry actual public-key material. No nonexistent upstream notice is invented.',
            'Exact Expat source-recipe transport limitation remains separate. This is notice preservation, not legal compatibility approval.'])
with (OUT/'proxy-inline-notices.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],source_files=len(files),verified=sum(row['result']=='verified_source_file' for row in files),inline_notices=len(notices))))
