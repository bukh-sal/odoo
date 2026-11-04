"""Actual selected host notices and official Node archive binding; no install."""
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-host-notices-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
lock=json.loads((ROOT/'deploy/host-toolchain.lock.json').read_text())
assert sys.version.split()[0]==lock['Python']=='3.12.16' and Path(sys.executable).resolve()==(ROOT/lock['selected_interpreter']).resolve()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def norm(name):return re.sub('[-_.]+','-',name).lower()
notice_pattern=re.compile(r'(?i)^(?:licen[cs]e|copying|copyright|notice|third.*notice)(?:$|[._-])')
notices={};index=[]
def preserve(name,path):
    raw=path.read_bytes();assert len(raw)<=16*1024*1024
    if name in notices:assert notices[name]==raw
    notices[name]=raw
    return dict(path=name,source_path=str(path),sha256=sha(raw),bytes=len(raw))
pins={norm(name):version for path in lock['python_dependencies'] for name,version in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)',(ROOT/path).read_text(),re.M)}
actual={norm(d.metadata['Name']):d for d in importlib.metadata.distributions()}
assert {name:d.version for name,d in actual.items()}==pins and len(actual)==13
python=[]
for key,d in sorted(actual.items()):
    rows=[]
    for file in d.files or []:
        path=Path(d.locate_file(file))
        if path.is_file() and notice_pattern.match(path.name):
            rows.append(preserve('host/operator-python/'+str(file).replace('\\','/'),path))
    assert rows,key
    python.append(dict(name=d.metadata['Name'],version=d.version,license_expression=d.metadata.get('License-Expression'),
        license_field=d.metadata.get('License'),license_classifiers=d.metadata.get_all('Classifier',[]),
        metadata_sha256=sha((Path(d._path)/'METADATA').read_bytes()),requires_dist=d.requires or [],notices=rows))
base=Path(sys.base_prefix);base_notices=[]
for path in sorted(base.rglob('*')):
    if path.is_file() and not path.is_symlink() and notice_pattern.match(path.name):
        base_notices.append(preserve('host/python-base/'+path.relative_to(base).as_posix(),path))
assert any(row['path']=='host/python-base/LICENSE.txt' for row in base_notices)
base_pip=base/'Lib/site-packages/pip-26.2.2.dist-info'
assert base_pip.is_dir() and str(base/'Lib/site-packages') not in sys.path
nodepath=Path(subprocess.check_output(['node','-p','process.execPath'],text=True).strip())
assert subprocess.check_output([str(nodepath),'--version'],text=True).strip()=='v'+lock['Node']
release='https://nodejs.org/download/release/v'+lock['Node']+'/'
with urllib.request.urlopen(release+'SHASUMS256.txt',timeout=30) as response:manifest=response.read(1024*1024)
(PRIVATE/'SHASUMS256.txt').write_bytes(manifest)
filename='node-v'+lock['Node']+'-win-x64.zip';matches=[line.split()[0] for line in manifest.decode().splitlines() if line.split()[-1]==filename]
assert len(matches)==1;expected=matches[0];archive=PRIVATE/filename;digest=hashlib.sha256();total=0
with urllib.request.urlopen(release+filename,timeout=45) as response,archive.open('xb') as stream:
    while True:
        raw=response.read(1024*1024)
        if not raw:break
        total+=len(raw);assert total<=96*1024*1024;digest.update(raw);stream.write(raw)
assert digest.hexdigest()==expected,'Official Node archive checksum differs; do not execute or install'
prefix=filename[:-4]+'/'
with zipfile.ZipFile(archive) as z:
    digest=hashlib.sha256()
    with z.open(prefix+'node.exe') as stream:
        while True:
            raw=stream.read(1024*1024)
            if not raw:break
            digest.update(raw)
    with nodepath.open('rb') as stream:installed=hashlib.file_digest(stream,'sha256').hexdigest()
    assert digest.hexdigest()==installed,'Installed Node differs from official archive; inspect before claiming provenance'
    node_license=z.read(prefix+'LICENSE');notices['host/node/LICENSE']=node_license
    node_notice=dict(path='host/node/LICENSE',sha256=sha(node_license),bytes=len(node_license))
    node_packages=[]
    for path in sorted((nodepath.parent/'node_modules').rglob('package.json')):
        if path.is_symlink():continue
        parts=path.relative_to(nodepath.parent).parts;last=max(n for n,p in enumerate(parts) if p=='node_modules');tail=parts[last+1:]
        if not (len(tail)==2 or len(tail)==3 and tail[0].startswith('@')):continue
        metadata=json.loads(path.read_text());root=path.parent;rows=[]
        for notice in sorted(root.iterdir()):
            if notice.is_file() and not notice.is_symlink() and notice_pattern.match(notice.name):
                rows.append(preserve('host/node/'+notice.relative_to(nodepath.parent).as_posix(),notice))
        relative=path.relative_to(nodepath.parent).as_posix()
        archive_metadata=z.read(prefix+relative)
        node_packages.append(dict(name=metadata['name'],version=metadata['version'],license=metadata.get('license'),
            metadata_path=relative,metadata_sha256=sha(path.read_bytes()),official_archive_metadata_exact=archive_metadata==path.read_bytes(),notices=rows))
    assert all(row['official_archive_metadata_exact'] for row in node_packages)
    assert next(row['version'] for row in node_packages if row['name']=='npm')==lock['npm']
typescript=[];npm_lock=json.loads((ROOT/'packages/host_sdk/package-lock.json').read_text())
for name in ['typescript','@typescript/typescript-win32-x64']:
    root=ROOT/'packages/host_sdk/node_modules'/name;metadata=json.loads((root/'package.json').read_text())
    pin=npm_lock['packages']['node_modules/'+name];assert metadata['version']==pin['version']==lock['TypeScript']
    rows=[preserve('host/typescript/'+name+'/'+path.name,path) for path in sorted(root.iterdir()) if path.is_file() and notice_pattern.match(path.name)]
    assert {Path(row['path']).name for row in rows}>={'LICENSE','NOTICE.txt'}
    typescript.append(dict(name=name,version=metadata['version'],license=metadata['license'],resolved=pin['resolved'],
        integrity=pin['integrity'],metadata_sha256=sha((root/'package.json').read_bytes()),notices=rows))
buffer=io.BytesIO();manifest_rows=[]
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in sorted(notices.items()):
        info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
        manifest_rows.append(dict(path=name,sha256=sha(raw),bytes=len(raw)))
bundle=buffer.getvalue();(PRIVATE/'host-notices.zip').write_bytes(bundle)
record=dict(result='passed_actual_selected_host_notice_collection',python=python,base_interpreter=dict(version=lock['Python'],
    base_prefix=str(base),provenance=lock['python_provenance'],notices=base_notices,
    bootstrap_pip=dict(version='26.2.2',included_in_selected_venv=False,metadata_sha256=sha((base_pip/'METADATA').read_bytes()))),
    node=dict(version=lock['Node'],executable=str(nodepath),executable_sha256=installed,archive_url=release+filename,
        archive_sha256=expected,archive_bytes=total,manifest_url=release+'SHASUMS256.txt',manifest_sha256=sha(manifest),
        installed_binary_matches_official_archive=True,notice=node_notice,bundled_packages=node_packages),
    typescript=typescript,notice_archive='.local/g7-host-notices-01/host-notices.zip',notice_archive_sha256=sha(bundle),files=manifest_rows,
    toolchain_lock_sha256=sha((ROOT/'deploy/host-toolchain.lock.json').read_bytes()),global_toolchain_or_runtime_mutations=0,
    limits=['Actual installed notice bytes and Node binary/metadata archive binding; no global install/update or execution of downloaded code.',
            'Base bootstrap pip is separately inventoried and not on the selected isolated operator path.',
            'Npm bundled package notice gaps, host/native vendor coverage and dated vulnerability dispositions require explicit review; not full OPS03/G7.'])
with (OUT/'host-notice-index.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],Python_packages=len(python),Node_bundled_packages=len(node_packages),notices=len(notices),Node_binary_official_exact=True)))
