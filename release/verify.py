"""Verify the local release kit's checksums. Checksums are not publisher authentication."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path,PurePosixPath

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def verify(root):
    root=Path(root).resolve()
    manifest=json.loads((root/'kit-inventory.json').read_bytes())
    if manifest.get('format')!='modular-platform-local-kit-1':raise ValueError('Unknown kit format')
    expected=set(manifest['files'])|{'kit-inventory.json','SHA256SUMS'}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=expected:raise ValueError('Missing or unexpected kit files')
    for name,row in manifest['files'].items():
        pure=PurePosixPath(name)
        if pure.is_absolute() or '..' in pure.parts or '\\' in name:raise ValueError('Invalid kit path')
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Linked kit member')
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('Kit checksum mismatch: '+name)
    lines=(root/'SHA256SUMS').read_text(encoding='utf8').splitlines()
    indexed={}
    for line in lines:
        value,name=line.split('  ',1)
        if name in indexed:raise ValueError('Duplicate checksum member')
        indexed[name]=value
    wanted={name:row['sha256'] for name,row in manifest['files'].items()}
    wanted['kit-inventory.json']=digest(root/'kit-inventory.json')
    if indexed!=wanted:raise ValueError('Checksum index differs from manifest')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('kit',type=Path);args=parser.parse_args()
    value=verify(args.kit)
    print(json.dumps(dict(result='verified_local_kit_checksums',source_commit=value['source_commit'],files=len(value['files']),stage=value['stage'])))
