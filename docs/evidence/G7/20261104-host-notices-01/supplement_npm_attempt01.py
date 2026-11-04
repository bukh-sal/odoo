"""Inspect exact public registry artifacts for missing bundled npm notices as data."""
import base64
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import re
import tarfile
import urllib.parse
import urllib.request

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-host-notices-01'
index=json.loads((OUT/'host-notice-index.json').read_text());gaps=[p for p in index['node']['bundled_packages'] if not p['notices']]
assert len(gaps)==4
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=30) as response:raw=response.read(16*1024*1024+1)
    assert len(raw)<=16*1024*1024
    return raw
rows=[]
for gap in gaps:
    name=gap['name'];version=gap['version'];safe=name.replace('@','').replace('/','--')
    metadata_url='https://registry.npmjs.org/'+urllib.parse.quote(name,safe='')+'/'+version
    raw=fetch(metadata_url);metadata=json.loads(raw);assert metadata['name']==name and metadata['version']==version
    (PRIVATE/(safe+'-metadata.json')).write_bytes(raw)
    url=metadata['dist']['tarball'];assert url.startswith('https://registry.npmjs.org/')
    raw=fetch(url);algorithm,digest=metadata['dist']['integrity'].split('-',1)
    assert algorithm=='sha512' and hashlib.sha512(raw).digest()==base64.b64decode(digest)
    path=PRIVATE/(safe+'.tgz');assert not path.exists();path.write_bytes(raw)
    notices=[]
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        package=archive.extractfile('package/package.json').read()
        installed=Path(index['node']['executable']).parent/gap['metadata_path']
        assert package==installed.read_bytes(),name+' installed manifest differs from exact registry artifact'
        for member in archive:
            pure=PurePosixPath(member.name);assert not pure.is_absolute() and '..' not in pure.parts
            if member.isfile() and re.match(r'(?i)^(?:licen[cs]e|copying|copyright|notice)(?:$|[._-])',pure.name):
                value=archive.extractfile(member).read();target=PRIVATE/(safe+'-'+pure.name)
                assert not target.exists();target.write_bytes(value)
                notices.append(dict(member=member.name,sha256=sha(value),bytes=len(value),private_file=target.relative_to(ROOT).as_posix()))
    rows.append(dict(name=name,version=version,license=gap['license'],metadata_url=metadata_url,metadata_sha256=sha((PRIVATE/(safe+'-metadata.json')).read_bytes()),
        tarball_url=url,tarball_sha512=metadata['dist']['integrity'],tarball_sha256=sha(raw),installed_manifest_exact=True,
        gitHead=metadata.get('gitHead'),repository=metadata.get('repository'),homepage=metadata.get('homepage'),notices=notices,
        result='exact_registry_notices_preserved' if notices else 'exact_registry_artifact_also_has_no_standalone_notice'))
report=dict(result='exact_npm_gap_artifacts_checked',records=rows,downloaded_code_executed=False,
    limits=['Exact source artifact inspection only. Remaining absent notices require version/commit-bound source attribution review; metadata alone is not a permission text.'])
with (OUT/'npm-supplement-artifacts.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],packages=4,with_notices=sum(bool(row['notices']) for row in rows))))
