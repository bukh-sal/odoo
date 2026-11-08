"""Finite persisted AT credential audit of kit/source/archives/new application layers."""
import argparse
import base64
import configparser
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--source-only',type=Path);a=p.parse_args();assert not a.receipt.exists()
    kit=a.kit.resolve();assert kit.is_relative_to(ROOT/'.local/releases')
    values=set();sources=[];local=ROOT/'.local/aurora-tasks'
    for path in local.rglob('account-passwords.json'):
        values.update(v for v in json.loads(path.read_bytes()).values() if isinstance(v,str) and len(v)>=16)
        sources.append(path.relative_to(ROOT).as_posix())
    for path in local.rglob('odoo.conf'):
        cfg=configparser.ConfigParser();cfg.read(path,encoding='utf-8')
        values.update(v for key in ('db_password','admin_passwd') if len(v:=cfg['options'].get(key,''))>=16)
        sources.append(path.relative_to(ROOT).as_posix())
    for path in local.rglob('db.env'):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('POSTGRES_PASSWORD='):values.add(line.split('=',1)[1])
        sources.append(path.relative_to(ROOT).as_posix())
    assert len(values)>=30 and len(sources)>=12
    patterns=set()
    for v in values:
        raw=v.encode();patterns.update((raw,v.encode('utf-16le'),base64.b64encode(raw),base64.urlsafe_b64encode(raw)))
    match=re.compile(b'|'.join(re.escape(v) for v in sorted(patterns)))
    totals=dict(files=0,unique_contents=0,bytes=0,archives=0);seen=set();findings=[]
    def scan(raw,label,depth=0):
        assert depth<=5 and len(raw)<=128*1024*1024
        totals['files']+=1;sha=hashlib.sha256(raw).hexdigest()
        if sha in seen:return
        seen.add(sha);totals['unique_contents']+=1;totals['bytes']+=len(raw)
        if match.search(raw):findings.append(dict(path=label,sha256=sha))
        if raw.startswith(b'PK\x03\x04'):
            totals['archives']+=1
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for entry in z.infolist():
                    if not entry.is_dir():
                        assert entry.file_size<=128*1024*1024
                        scan(z.read(entry),label+'!'+entry.filename,depth+1)
    manifest=json.loads((kit/'kit-inventory.json').read_bytes())
    for name in manifest['files']:
        if name=='images.tar':continue
        if name=='source.zip':
            totals['archives']+=1
            with zipfile.ZipFile(kit/name) as z:
                for entry in z.infolist():
                    if not entry.is_dir():scan(z.read(entry),name+'!'+entry.filename)
        else:scan((kit/name).read_bytes(),name)
    image=json.loads((kit/'images.json').read_bytes())['images'];archive_sha=digest(kit/'images.tar');layers=[]
    if a.source_only:
        old=json.loads(a.source_only.read_bytes())
        assert old['result']=='passed_finite_persisted_AT_values' and old['images_tar_sha256']==archive_sha
        assert old['image']==image['application']['image_id'] and old['known_values']==len(values)
    else:
        app,=json.loads(subprocess.check_output(['docker','image','inspect',image['application']['image_id']]))
        dep,=json.loads(subprocess.check_output(['docker','image','inspect',image['dependency_base']['image_id']]))
        all_layers=app['RootFS']['Layers'];base=dep['RootFS']['Layers'];assert all_layers[:len(base)]==base
        scan(json.dumps(app,sort_keys=True).encode(),'application-image-metadata')
        with tarfile.open(kit/'images.tar','r:*') as outer:
            matches=[]
            for entry in json.load(outer.extractfile('manifest.json')):
                config=json.load(outer.extractfile(entry['Config']))
                if config['rootfs']['diff_ids']==all_layers:matches.append(entry)
            selected,=matches;assert len(selected['Layers'])==len(all_layers)
            for name in selected['Layers'][len(base):]:
                with tarfile.open(fileobj=outer.extractfile(name),mode='r|*') as layer:
                    for row in layer:
                        if row.isfile():
                            assert row.size<=128*1024*1024
                            scan(layer.extractfile(row).read(),'new-layer:'+name+'!'+row.name)
                layers.append(name)
    report=dict(result='failed_known_value' if findings else 'passed_finite_persisted_AT_values',
        image=image['application']['image_id'],kit_source=manifest['source_commit'],kit_manifest_sha256=digest(kit/'kit-inventory.json'),
        images_tar_sha256=archive_sha,known_values=len(values),encodings=len(patterns),credential_sources=sources,
        totals=totals,findings=findings,new_application_layers=layers,prior_full_receipt=str(a.source_only) if a.source_only else None,
        limits=['Finite persisted AT fixture login/master/database values in literal/UTF16LE/Base64 forms, not an unknown-secret detector.',
            'Transient probe credentials that were never retained on the host cannot be enumerated; generated config/data paths are excluded from build inputs.',
            'Unchanged pinned dependency/toolchain/notice artifacts retain previous qualification; this is no publisher authentication or production security claim.'])
    a.receipt.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not findings,'Inspect named private value finding; never print its value'
    print(json.dumps(dict(result=report['result'],known_values=len(values),files=totals['files'],findings=len(findings))))


if __name__=='__main__':main()
