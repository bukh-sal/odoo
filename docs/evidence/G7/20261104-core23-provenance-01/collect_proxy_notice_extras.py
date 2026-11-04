"""Complete declared extra source archives and FreeType's referenced license texts."""
import ast
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-source-notices-01'
archives=PRIVATE/'archives';blobs=ROOT/'third_party/alpine-notices/texts'
source=(OUT/'collect_proxy_notices.py').read_text();tree=ast.parse(source)
function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='collect')
owned_code=ast.get_source_segment(source,function)
assert owned_code.count('digest,name=candidates[0]')==1
owned_code=owned_code.replace('digest,name=candidates[0]','digest,name=candidates[row["archive_choice"]]')
name_pattern=re.compile(r'(?i)(?:licen[cs]e|copying|copyright|notice|patents|authors|gpl|lgpl|agpl|bsd|mit)(?:[._-].*)?$|(?:FTL|GPLv[0-9]+|LGPLv[0-9]+)\..*')
archive_pattern=re.compile(r'\.(?:tar\.(?:gz|bz2|xz)|tgz|tbz2|txz|zip)$')
def sha(raw):return hashlib.sha256(raw).hexdigest()
exec(compile(owned_code,'owned-archive-reader-extra-choice.py','exec'),globals())
recipes=json.loads((OUT/'proxy-source-recipes.json').read_text())['records']
primary=json.loads((OUT/'proxy-source-notices.json').read_text())['records']
records=[]
for previous in primary:
    if not previous.get('additional_source_archives'):continue
    row=next(row for row in recipes if row['origin']==previous['origin'])
    for n,extra in enumerate(previous['additional_source_archives'],1):
        archive=archives/extra['name'];assert archive.parent==archives
        if not archive.exists():
            url='https://distfiles.alpinelinux.org/distfiles/v3.24/'+urllib.parse.quote(extra['name'],safe='')
            total=0
            with urllib.request.urlopen(url,timeout=45) as response,archive.open('xb') as stream:
                while True:
                    raw=response.read(1024*1024)
                    if not raw:break
                    total+=len(raw);assert total<=128*1024*1024;stream.write(raw)
        with archive.open('rb') as stream:assert hashlib.file_digest(stream,'sha512').hexdigest()==extra['sha512']
        found=[]
        with tarfile.open(archive) as t:
            for member in t:
                path=PurePosixPath(member.name)
                assert not path.is_absolute() and '..' not in path.parts
                if not member.isfile() or not name_pattern.fullmatch(path.name):continue
                assert member.size<2*1024*1024
                raw=t.extractfile(member).read();digest=sha(raw);destination=blobs/(digest+'.txt')
                if destination.exists():assert destination.read_bytes()==raw
                else:destination.write_bytes(raw)
                found.append(dict(member=member.name,bytes=len(raw),sha256=digest,path=destination.relative_to(ROOT).as_posix()))
        records.append(dict(origin=row['origin'],source_archive=extra['name'],source_sha512=extra['sha512'],
            recipe_sha256=row['sha256'],private_archive=archive.relative_to(ROOT).as_posix(),notices=found,
            result='verified_additional_source_notices_preserved' if found else 'verified_additional_source_no_standalone_notice',
            origin_primary_notices=previous['notices']))
ft=next(row for row in primary if row['origin']=='freetype')
archive=ROOT/ft['private_archive']
with archive.open('rb') as stream:assert hashlib.file_digest(stream,'sha512').hexdigest()==ft['source_sha512']
referenced=[]
with tarfile.open(archive) as t:
    for path in ['freetype-2.14.3/docs/FTL.TXT','freetype-2.14.3/docs/GPLv2.TXT']:
        member=t.getmember(path);assert member.isfile() and member.size<1024*1024
        raw=t.extractfile(member).read();digest=sha(raw);destination=blobs/(digest+'.txt')
        if destination.exists():assert destination.read_bytes()==raw
        else:destination.write_bytes(raw)
        referenced.append(dict(origin='freetype',source_sha512=ft['source_sha512'],member=path,sha256=digest,
                               bytes=len(raw),path=destination.relative_to(ROOT).as_posix()))
report=dict(result='passed_declared_additional_sources_and_referenced_freetype_license_texts',
    additional_source_archives=records,referenced_license_files=referenced,
    owned_reader_source_sha256=sha(source.encode()),owned_reader_adapted_sha256=sha(owned_code.encode()),
    upstream_scripts_executed=False,source_installed=False,
    limits=['Only exact declared additional source checksums are accepted; an existing completed transfer is reused after full SHA512 verification. No shell evaluation.',
            'Alpine base/key/source-header and Expat notice coverage remain separate obligations.'])
with (OUT/'proxy-notice-extras.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],extra_archives=len(records),FreeType_referenced_texts=len(referenced))))
