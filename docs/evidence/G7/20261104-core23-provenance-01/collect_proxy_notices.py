"""Read license texts from checksum-verified upstream source archives, never install."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-source-notices-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
archives=protect_directory(PRIVATE/'archives');blobs=ROOT/'third_party/alpine-notices/texts'
assert not blobs.exists();blobs.mkdir(parents=True)
recipes=json.loads((OUT/'proxy-source-recipes.json').read_text())['records']
name_pattern=re.compile(r'(?i)(?:licen[cs]e|copying|copyright|notice|patents|authors|gpl|lgpl|agpl|bsd|mit)(?:[._-].*)?$')
archive_pattern=re.compile(r'\.(?:tar\.(?:gz|bz2|xz)|tgz|tbz2|txz|zip)$')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def collect(row):
    origin=row['origin']
    if row['result']!='recipe_preserved_as_data':return dict(origin=origin,result='exact_recipe_unavailable')
    recipe=(ROOT/row['private_file']).read_bytes();assert sha(recipe)==row['sha256']
    checksums=re.findall(r'^([0-9a-f]{128})  ([^\r\n]+)$',recipe.decode(),re.M)
    candidates=[(digest,name) for digest,name in checksums if archive_pattern.search(name)]
    if not candidates:return dict(origin=origin,result='no_source_archive_in_recipe',recipe_sha256=row['sha256'])
    # First archive is the primary source. Additional bundled sources are
    # explicitly retained as a remaining obligation, never silently covered.
    digest,name=candidates[0]
    assert PurePosixPath(name).name==name and re.fullmatch('[A-Za-z0-9+_.-]+',name)
    url='https://distfiles.alpinelinux.org/distfiles/v3.24/'+urllib.parse.quote(name,safe='')
    path=archives/name;assert not path.exists();total=0;hasher=hashlib.sha512()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=45) as response:
            with path.open('xb') as stream:
                while True:
                    raw=response.read(1024*1024)
                    if not raw:break
                    total+=len(raw)
                    if total>128*1024*1024:raise ValueError('Source archive exceeds declared 128MiB bound')
                    hasher.update(raw);stream.write(raw)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as error:
        return dict(origin=origin,result='source_fetch_incomplete',url=url,error=type(error).__name__,
                    status=getattr(error,'code',None),bytes=total,private_archive=path.relative_to(ROOT).as_posix())
    if hasher.hexdigest()!=digest:
        return dict(origin=origin,result='source_checksum_mismatch',url=url,bytes=total,expected_sha512=digest,
                    actual_sha512=hasher.hexdigest(),private_archive=path.relative_to(ROOT).as_posix())
    found=[];contents=[];expanded=0
    def consider(name,size,read):
        nonlocal expanded
        expanded+=size
        if expanded>2*1024**3:raise ValueError('Source decompressed size bound exceeded')
        parts=PurePosixPath(name)
        if parts.is_absolute() or '..' in parts.parts:raise ValueError('Unsafe archive member path')
        if not name_pattern.fullmatch(parts.name):return
        if size>2*1024*1024:raise ValueError('Notice member exceeds2MiB')
        raw=read()
        if len(raw)!=size:raise ValueError('Truncated archive notice')
        if b'\x00' in raw[:4096]:return
        if sum(row['bytes'] for row in found)+len(raw)>8*1024*1024:raise ValueError('Notice aggregate bound exceeded')
        digest=sha(raw);contents.append((digest,raw));found.append(dict(member=name,bytes=len(raw),sha256=digest,
            path='third_party/alpine-notices/texts/'+digest+'.txt'))
    try:
        if name.endswith('.zip'):
            with zipfile.ZipFile(path) as z:
                for member in z.infolist():
                    if not member.is_dir():consider(member.filename,member.file_size,lambda member=member:z.read(member))
        else:
            with tarfile.open(path,'r|*') as t:
                for member in t:
                    if member.isfile():consider(member.name,member.size,lambda member=member:t.extractfile(member).read())
    except (ValueError,tarfile.TarError,zipfile.BadZipFile) as error:
        return dict(origin=origin,result='source_notice_collection_incomplete',url=url,expected_sha512=digest,
                    bytes=total,error=type(error).__name__,notices=found,private_archive=path.relative_to(ROOT).as_posix())
    # Parent writes deduplicated immutable blobs, avoiding concurrent writes.
    return dict(origin=origin,result='verified_primary_source_notices_preserved' if found else 'verified_source_no_standalone_notice',
        packages=row['packages'],installed_versions=row['installed_versions'],source_commit=row['source_commit'],
        recipe_url=row['url'],recipe_sha256=row['sha256'],source_url=url,source_archive=name,source_bytes=total,
        source_sha512=digest,private_archive=path.relative_to(ROOT).as_posix(),notices=found,
        additional_source_archives=[dict(name=n,sha512=d) for d,n in candidates[1:]],_contents=contents)
records=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for result in pool.map(collect,recipes):
        for digest,raw in result.pop('_contents',[]):
            path=blobs/(digest+'.txt')
            if path.exists():assert path.read_bytes()==raw
            else:path.write_bytes(raw)
        records.append(result)
        if len(records)%8==0:print(json.dumps(dict(completed=len(records),of=len(recipes))),flush=True)
record=dict(result='checksum_verified_proxy_source_notices_collected_review_pending',origins=len(records),records=records,
    source_recipes_executed=False,code_installed=False,archive_members_extracted_to_filesystem=False,
    limits=['Only matching standalone notice/license/attribution text is preserved as opaque bytes. This is not a compatibility opinion.',
            'Additional bundled source archives, origins without archive/license files and exact Expat recipe availability remain explicit coverage gaps.',
            'Verified compressed source archives are private retained provenance inputs; preserve or retire with exact receipts, never global cleanup.'])
with (OUT/'proxy-source-notices.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],origins=len(records),with_notices=sum(bool(r.get('notices')) for r in records),
    unique_notice_blobs=len(list(blobs.iterdir())),source_bytes=sum(r.get('source_bytes',r.get('bytes',0)) for r in records))))
