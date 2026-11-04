"""Use the exact recipe's content digest for its timestamp-varying Gitiles archive."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import tarfile

ROOT=Path.cwd();OUT=Path(__file__).parent
recipes=json.loads((OUT/'proxy-source-recipes.json').read_text())['records']
recipe=next(row for row in recipes if row['origin']=='libyuv')
raw=(ROOT/recipe['private_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==recipe['sha256']
text=raw.decode();expected=re.search(r'^_libyuvchecksum=([0-9a-f]{128})$',text,re.M).group(1)
commit=re.search(r'^_commit=([0-9a-f]{40})$',text,re.M).group(1)
assert 'find . -type f | sort | xargs cat | sha512sum' in text
assert 'different timestamps, thus different checksums' in text
prior=json.loads((OUT/'proxy-source-notices.json').read_text())
source=next(row for row in prior['records'] if row['origin']=='libyuv');assert source['result']=='source_checksum_mismatch'
archive=ROOT/source['private_archive'];files=[]
with tarfile.open(archive) as t:
    for member in t:
        name=str(PurePosixPath(member.name))
        assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
        if member.isfile():
            assert member.size<16*1024*1024
            files.append((name,member))
    assert len({name for name,_ in files})==len(files)
    digest=hashlib.sha512()
    for name,member in sorted(files):
        raw=t.extractfile(member).read();assert len(raw)==member.size;digest.update(raw)
    assert digest.hexdigest()==expected,'Content does not match the exact package recipe; do not relabel the archive'
    notices=[]
    for name,member in files:
        if PurePosixPath(name).name not in {'LICENSE','PATENTS','AUTHORS','NOTICE','COPYING'}:continue
        raw=t.extractfile(member).read();sha=hashlib.sha256(raw).hexdigest()
        path=ROOT/'third_party/alpine-notices/texts'/(sha+'.txt')
        if path.exists():assert path.read_bytes()==raw
        else:path.write_bytes(raw)
        notices.append(dict(member=name,bytes=len(raw),sha256=sha,path=path.relative_to(ROOT).as_posix()))
assert any(PurePosixPath(row['member']).name=='LICENSE' for row in notices)
record=dict(result='passed_exact_libyuv_recipe_prescribed_source_content_digest',origin='libyuv',
    source_commit=commit,recipe=recipe,raw_archive_sha512=source['actual_sha512'],
    raw_archive_checksum_mismatch_retained=True,recipe_content_sha512=expected,actual_content_sha512=digest.hexdigest(),
    ordered_regular_files=len(files),notices=notices,recipe_or_shell_executed=False,
    explanation='The exact installed recipe explicitly bypasses the timestamp-varying Gitiles TAR digest and checks concatenated sorted regular-file contents before patches. The same content digest is verified here without executing its shell.',
    limits=['Specific to this exact recipe/content hash. Generic checksum mismatches remain refused. No build or source patch is executed.'])
with (OUT/'libyuv-content-binding.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],files=len(files),notices=len(notices))))
