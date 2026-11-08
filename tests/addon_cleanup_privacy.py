"""Finite AR generated-login/master/database credential audit; no secret detector claim."""
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
KIT=ROOT/'.local/releases/foundation-r1-core47'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',required=True,type=Path)
    p.add_argument('--source-only',type=Path);a=p.parse_args();assert not a.receipt.exists()
    local=ROOT/'.local/addon-cleanup'
    roots=[local/name/'private/reference' for name in ('baseline46','aurora46','fault46','consumer47')]
    roots += [local/'profiles/ar04-peer-01/aurora']
    roots += [local/'profiles/ar05-clean-01'/name for name in ('core','aurora','maintenance')]
    roots += [local/'profiles/ar05-native-01'/name for name in ('regression','layout-regression')]
    values=set();sources=[]
    for root in roots:
        accounts=root/'account-passwords.json'
        if accounts.exists():
            values.update(v for v in json.loads(accounts.read_bytes()).values() if isinstance(v,str) and len(v)>=16)
            sources.append(accounts.relative_to(ROOT).as_posix())
        conf=root/'odoo.conf'
        if conf.exists():
            config=configparser.ConfigParser();config.read(conf,encoding='utf8')
            values.update(v for key in ('db_password','admin_passwd') if len(v:=config['options'].get(key,''))>=16)
            sources.append(conf.relative_to(ROOT).as_posix())
    assert values and len(sources)>=16
    patterns=set()
    for value in values:
        raw=value.encode('utf8');patterns.update((raw,value.encode('utf-16le'),base64.b64encode(raw),base64.urlsafe_b64encode(raw)))
    match=re.compile(b'|'.join(re.escape(v) for v in sorted(patterns)))
    seen=set();findings=[];totals=dict(files=0,unique_contents=0,bytes=0,archives=0)
    def scan(raw,label,depth=0):
        assert depth<=5 and len(raw)<=128*1024*1024,'Explicit nested archive bounds exceeded'
        totals['files']+=1;sha=hashlib.sha256(raw).hexdigest()
        if sha in seen:return
        seen.add(sha);totals['unique_contents']+=1;totals['bytes']+=len(raw)
        if match.search(raw):findings.append(dict(path=label,sha256=sha))
        if raw.startswith(b'PK\x03\x04'):
            totals['archives']+=1
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for item in z.infolist():
                    if not item.is_dir():
                        assert item.file_size<=128*1024*1024
                        scan(z.read(item),label+'!'+item.filename,depth+1)
    manifest=json.loads((KIT/'kit-inventory.json').read_bytes())
    for name in manifest['files']:
        if name=='images.tar':continue
        if name=='source.zip':
            totals['archives']+=1
            with zipfile.ZipFile(KIT/name) as z:
                for item in z.infolist():
                    if not item.is_dir():
                        assert item.file_size<=128*1024*1024
                        scan(z.read(item),name+'!'+item.filename)
        else:scan((KIT/name).read_bytes(),name)
    def digest(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    image=json.loads((KIT/'images.json').read_bytes())['images'];archive_sha=digest(KIT/'images.tar');layers=[]
    if a.source_only:
        old=json.loads(a.source_only.read_bytes())
        assert old['result']=='passed_finite_known_values' and old['images_tar_sha256']==archive_sha
        assert old['image']==image['application']['image_id'] and old['known_values']==len(values)
    else:
        app,=json.loads(subprocess.check_output(['docker','image','inspect',image['application']['image_id']]))
        dep,=json.loads(subprocess.check_output(['docker','image','inspect',image['dependency_base']['image_id']]))
        all_layers=app['RootFS']['Layers'];base=dep['RootFS']['Layers'];assert all_layers[:len(base)]==base
        scan(json.dumps(app,sort_keys=True).encode(),'application-image-metadata')
        with tarfile.open(KIT/'images.tar','r:*') as outer:
            candidates=[]
            for entry in json.load(outer.extractfile('manifest.json')):
                config=json.load(outer.extractfile(entry['Config']))
                if config['rootfs']['diff_ids']==all_layers:candidates.append(entry)
            selected,=candidates;assert len(selected['Layers'])==len(all_layers)
            for name in selected['Layers'][len(base):]:
                with tarfile.open(fileobj=outer.extractfile(name),mode='r|*') as layer:
                    for row in layer:
                        if row.isfile():
                            assert row.size<=128*1024*1024
                            scan(layer.extractfile(row).read(),'new-layer:'+name+'!'+row.name)
                layers.append(name)
    report=dict(result='failed_known_value' if findings else 'passed_finite_known_values',
        image=image['application']['image_id'],kit_source=manifest['source_commit'],kit_manifest_sha256=digest(KIT/'kit-inventory.json'),
        images_tar_sha256=archive_sha,known_values=len(values),encodings=len(patterns),credential_sources=sources,
        totals=totals,findings=findings,new_application_layers=layers,prior_full_receipt=str(a.source_only) if a.source_only else None,
        limits=['Only known generated AR fixture login/master/database credential values; not an unknown-secret detector or publisher authentication.',
                'Static fictional test literals are intentional source fixtures, not private generated credentials.',
                'Source, curated archives, support files and new application layers decoded; unchanged dependency/support images retain their prior audit scope.',
                'Nested ZIP depth<=5; individual files<=128MiB. No private payloads or credential values appear in this report.'])
    a.receipt.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(result=report['result'],known_values=len(values),totals=totals,findings=len(findings))))
    assert not findings


if __name__=='__main__':main()
