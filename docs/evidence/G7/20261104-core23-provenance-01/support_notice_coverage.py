"""Resolve actual retained documentation links; preserve all support identities."""
import hashlib
import json
from pathlib import Path
import posixpath
import tarfile
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_bytes())
support=load(ROOT/'docs/evidence/G7/20261104-support-images-01/inventory.json')
bundles=load(ROOT/'docs/evidence/G7/20261104-image-secret-audit-01/support-notice-bundles.json')['roles']
archive=ROOT/'.local/g7-image-secret-audit-01/postgres-documentation.zip'
assert sha(archive.read_bytes())==bundles['postgres']['archive_sha256']
with tarfile.open(ROOT/'.local/g7-image-secret-audit-01/postgres-documentation.tar') as t:
    members={member.name.rstrip('/'):member for member in t}
    def resolve(name):
        chain=[]
        for _ in range(16):
            parts=name.split('/');changed=False
            for n in range(1,len(parts)+1):
                prefix='/'.join(parts[:n]);member=members.get(prefix)
                if member is not None and member.issym():
                    target=posixpath.normpath(posixpath.join(posixpath.dirname(prefix),member.linkname))
                    assert target.startswith('usr/share/doc/') and '..' not in target.split('/')
                    chain.append(dict(path=prefix,target=target))
                    name=posixpath.join(target,*parts[n:]);changed=True;break
                if member is not None and member.islnk():
                    target=posixpath.normpath(member.linkname.lstrip('/'))
                    assert target.startswith('usr/share/doc/') and '..' not in target.split('/')
                    chain.append(dict(path=prefix,target=target));name=posixpath.join(target,*parts[n:]);changed=True;break
            if not changed:return name,chain
        raise ValueError('Documentation link cycle or unsupported depth')
    rows=[]
    with zipfile.ZipFile(archive) as z:
        for package in support['roles']['postgres']['packages']:
            expected='usr/share/doc/'+package['name']+'/copyright'
            resolved,chain=resolve(expected);raw=z.read(resolved)
            assert members[resolved].isfile() and t.extractfile(members[resolved]).read()==raw
            rows.append(package|dict(copyright=dict(requested_path=expected,resolved_path=resolved,
                archive_sha256=bundles['postgres']['archive_sha256'],sha256=sha(raw),bytes=len(raw),link_chain=chain)))
assert len(rows)==144 and all(row['copyright']['bytes']>0 for row in rows)
raw=(ROOT/'.local/g7-support-images-02/proxy-candidate-solution.stdout').read_bytes();_,body=raw.decode().split('\n',1)
proxy=[]
for block in body.split('\n\n'):
    fields={line[:1]:line[2:] for line in block.splitlines() if len(line)>1 and line[1]==':'}
    if fields:
        proxy.append(dict(name=fields['P'],version=fields['V'],origin=fields.get('o'),license=fields.get('L'),
            architecture=fields.get('A'),source_commit=fields.get('c'),description=fields.get('T')))
assert len(proxy)==71 and all(package['license'] for package in proxy)
proxy_archive=ROOT/'.local/g7-image-secret-audit-01/proxy-documentation.zip'
assert sha(proxy_archive.read_bytes())==bundles['proxy']['archive_sha256']
with zipfile.ZipFile(proxy_archive) as z:
    for row in bundles['proxy']['files']:
        raw=z.read(row['path']);assert sha(raw)==row['sha256'] and len(raw)==row['bytes']
record=dict(result='passed_postgres_complete_notice_link_coverage_proxy_supplements_pending',
    postgres=dict(image=support['roles']['postgres']['pinned_reference'],packages=rows,packages_with_notices=144,
        reused_archive=archive.relative_to(ROOT).as_posix(),archive_sha256=bundles['postgres']['archive_sha256'],
        exact_documentation_aliases=sum(bool(row['copyright']['link_chain']) for row in rows)),
    proxy=dict(image='modular-platform-proxy@sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f',
        packages=proxy,source_collection_sha256=sha((ROOT/'.local/g7-support-images-02/proxy-candidate-solution.stdout').read_bytes()),
        shipped_documents=bundles['proxy']['files'],archive_sha256=bundles['proxy']['archive_sha256'],
        missing_standalone_notice_supplements_require_review=True),
    no_new_collector_or_archive=True,
    limits=['All144 PostgreSQL package copyright paths resolve to141 preserved actual files; three directory aliases are explicit, not missing notices.',
            'Alpine metadata declares licenses but does not supply all upstream license text. Exact source-origin/commit supplements remain required before OPS03.',
            'Notice/source preservation only; no proprietary relicensing, publication permission or legal compatibility opinion.'])
with (OUT/'support-notice-coverage.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],PG_packages=144,PG_aliases=3,proxy_packages=71)))
