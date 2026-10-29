"""Retain missing upstream notice files from exact hash-locked source archives; execute nothing."""
import hashlib,io,json,re,sys,tarfile,urllib.request
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
LOCAL=ROOT/'.local/g5-provenance';target=ROOT/'third_party/python';assert not target.exists()
(LOCAL/'downloads').mkdir();target.mkdir(parents=True)
lock=(ROOT/'deploy/requirements-r1.lock').read_text();records=[]
for name,version in [('geoip2','2.9.0'),('pyserial','3.5'),('xlwt','1.3.0')]:
    metadata_url='https://pypi.org/pypi/'+name+'/'+version+'/json'
    with urllib.request.urlopen(metadata_url,timeout=30) as response:metadata=json.load(response)
    candidates=[f for f in metadata['urls'] if f['packagetype']=='sdist'];assert len(candidates)==1
    source=candidates[0];digest=source['digests']['sha256'];assert '--hash=sha256:'+digest in lock
    assert source['url'].startswith('https://files.pythonhosted.org/') and source['size']<20*1024*1024
    with urllib.request.urlopen(source['url'],timeout=30) as response:raw=response.read(20*1024*1024+1)
    assert len(raw)==source['size'] and hashlib.sha256(raw).hexdigest()==digest
    (LOCAL/'downloads'/source['filename']).write_bytes(raw);files=[]
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        for member in archive.getmembers():
            if not member.isfile():continue
            parts=PurePosixPath(member.name);basename=parts.name.lower()
            if not any(word in basename for word in ['license','licence','copying','copyright','notice']):continue
            assert member.size<1024*1024 and '..' not in parts.parts and not parts.is_absolute()
            content=archive.extractfile(member).read();relative=Path(name+'-'+version)/Path(*parts.parts[1:]);path=target/relative
            assert path.resolve().is_relative_to(target.resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            files.append(dict(path=path.relative_to(ROOT).as_posix(),archive_member=member.name,sha256=hashlib.sha256(content).hexdigest(),bytes=len(content)))
    assert files,'Inspect source archive without executing package setup'
    records.append(dict(name=name,version=version,source_metadata=metadata_url,archive_url=source['url'],archive_sha256=digest,locked_hash_verified=True,notices=files))
(OUTPUT/'supplemental-notices.json').write_text(json.dumps(dict(result='passed_retained_exact_upstream_notices',packages=records,reason='Installed distributions lacked standalone notices in RECORD. Supplement the associated distribution with exact source-archive notice files; no install/build/import or immutable runtime mutation.'),indent=2)+'\n')
print(json.dumps(dict(result='retained_exact_notices',packages=len(records),files=sum(len(r['notices']) for r in records))))
