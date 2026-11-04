"""Assemble one draft R1 kit from qualified local artifacts, never active control/data."""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(Path(__file__).parent)]
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
from verify import digest,verify

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--trust',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'.local/releases'):raise ValueError('Fresh project-owned .local/releases path required')
    if subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode:raise ValueError('Commit source before packaging')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    protect_directory(output)
    state=dict(phase='assembling',source_commit=head,completed_files={})
    receipt=args.receipt.resolve();receipt.parent.mkdir(parents=True,exist_ok=True)
    if receipt.exists():raise ValueError('Fresh receipt required')
    def phase(name):
        state['phase']=name
        receipt.with_suffix('.state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
        print(json.dumps(dict(phase=name)),flush=True)
    def register(name):
        path=output/name
        state['completed_files'][name]=dict(bytes=path.stat().st_size,sha256=digest(path))
    def copy(source,name,expected=None):
        source=Path(source)
        if expected and digest(source)!=expected:raise ValueError('Input checksum mismatch: '+name)
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        with source.open('rb') as original,target.open('xb') as dest:shutil.copyfileobj(original,dest)
        if digest(target)!=digest(source):raise ValueError('Copy checksum mismatch')
        register(name)
    def write(name,value):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf8') as stream:json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')
        register(name)
    def download(url,name,expected):
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        # A failed transfer never becomes a completed kit component.
        with urllib.request.urlopen(url,timeout=90) as response:raw=response.read()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Download checksum mismatch')
        with target.open('xb') as stream:stream.write(raw)
        register(name)
    runtime=json.loads((ROOT/'deploy/runtime.lock.json').read_bytes())
    reproduction=json.loads((ROOT/'docs/evidence/G7/20261104-core23-repro-01/qualification.json').read_bytes())
    worker=json.loads((ROOT/'services/document_stats/image.lock.json').read_bytes())
    selected={'application':reproduction['reference_image'],'dependency_base':reproduction['dependency_base'],
              'worker':worker['reference'],'postgres':runtime['postgres_image'],'proxy':runtime['reverse_proxy_image']}
    images={}
    for role,reference in selected.items():
        data=json.loads(subprocess.check_output(['docker','image','inspect',reference]))[0]
        images[role]=dict(image_id=data['Id'],source_reference=reference,architecture=data['Architecture'],OS=data['Os'])
    # Docker's digest-form export omits repository names too. A checked local
    # tag carries the repository binding through save/load; authority still
    # selects and verifies the immutable digest, never this mutable tag.
    worker_tag='modular-document-stats:release-'+worker['image_id'][7:19]
    existing=subprocess.run(['docker','image','inspect',worker_tag],capture_output=True)
    if existing.returncode==0:
        if json.loads(existing.stdout)[0]['Id']!=worker['image_id']:raise ValueError('Release worker tag already names different bytes')
    else:subprocess.run(['docker','image','tag',worker['image_id'],worker_tag],check=True)
    images['worker']['archive_reference']=worker_tag
    actual=inspect_image(images['application']['image_id'])
    if actual['inventory_digest']!=reproduction['inventory_digest']:raise ValueError('Unqualified app inventory')
    write('images.json',dict(images=images,application_inventory_digest=actual['inventory_digest'],platform_version=actual['platform_version']))
    phase('verified_catalog')
    validator=configuration(args.trust);catalog=Catalog(args.catalog,validator,readonly=True)
    packages=[]
    for descriptor in catalog.snapshot():
        value=descriptor['digest'];path=catalog.path(value);checked=validator.verify(path,expected_digest=value)
        name='plugins/'+value[7:]+'.mplug';copy(path,name,value[7:])
        packages.append(dict(file=name,digest=value,plugin_id=descriptor['plugin_id'],version=descriptor['version'],entries=len(checked.inventory)))
    if len(packages)<19:raise ValueError('Incomplete reference catalog')
    write('plugins/index.json',dict(packages=packages))
    # Digest curation is a portable reference allowlist, never executor approval.
    write('plugins/curated-trust.json',dict(schema_version=1,mode='curated',approved_digests=[p['digest'] for p in packages],allow_unsigned_development=False,generation=1))
    phase('retaining_notices')
    notice_inputs={
        'application':ROOT/'.local/g7-core22-provenance-01/application-notices.zip',
        'worker':ROOT/'.local/g7-core22-provenance-01/worker-notices.zip',
        'postgres':ROOT/'.local/g7-image-secret-audit-01/postgres-documentation.zip',
        'proxy':ROOT/'.local/g7-image-secret-audit-01/proxy-documentation.zip',
        'host':ROOT/'.local/g7-host-notices-01/host-notices-final.zip',
        'source':ROOT/'.local/g7-source-notices-01/release-notices.zip',
    }
    support=json.loads((ROOT/'docs/evidence/G7/20261104-image-secret-audit-01/support-notice-bundles.json').read_bytes())['roles']
    notice_hashes={
        'application':json.loads((ROOT/'docs/evidence/G7/20261104-core22-provenance-01/notice-bundle.json').read_bytes())['archive_sha256'],
        'worker':json.loads((ROOT/'docs/evidence/G7/20261104-core22-provenance-01/worker-notice-bundle.json').read_bytes())['archive_sha256'],
        'postgres':support['postgres']['archive_sha256'],'proxy':support['proxy']['archive_sha256'],
        'host':json.loads((ROOT/'docs/evidence/G7/20261104-host-notices-01/host-notices-final.json').read_bytes())['archive_sha256'],
        'source':json.loads((ROOT/'docs/evidence/G7/20261104-source-notices-01/notice-bundle.json').read_bytes())['archive_sha256'],
    }
    for role,path in notice_inputs.items():
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:raise ValueError('Notice ZIP CRC mismatch')
        copy(path,'notices/'+role+'.zip',notice_hashes[role])
    phase('retaining_toolchain')
    toolchain=json.loads((ROOT/'deploy/host-toolchain.lock.json').read_bytes())
    python=toolchain['python_provenance']
    download(python['archive_url'],'toolchain/python-windows.tar.gz',python['archive_sha256'])
    node=ROOT/'.local/g7-host-notices-01/node-v24.22.1-win-x64.zip'
    sums=(ROOT/'.local/g7-host-notices-01/SHASUMS256.txt').read_text()
    expected=next(line.split()[0] for line in sums.splitlines() if line.split()[-1]==node.name)
    copy(node,'toolchain/node-windows.zip',expected)
    for name in ['requirements-tooling.lock','requirements-operator.lock','host-toolchain.lock.json']:
        copy(ROOT/'deploy'/name,'toolchain/'+name)
    wheels=output/'toolchain/wheels';wheels.mkdir()
    base_python=Path(sys._base_executable)
    command=[str(base_python),'-I','-m','pip','--isolated','--disable-pip-version-check','download','--index-url','https://pypi.org/simple',
             '--require-hashes','--only-binary=:all:','--no-deps','--progress-bar','off','-r',str(ROOT/'deploy/requirements-tooling.lock'),
             '-r',str(ROOT/'deploy/requirements-operator.lock'),'-d',str(wheels)]
    with receipt.with_suffix('.pip.stdout').open('xb') as out,receipt.with_suffix('.pip.stderr').open('xb') as err:
        result=subprocess.run(command,cwd=ROOT,stdout=out,stderr=err,timeout=240)
    if result.returncode:raise RuntimeError('Inspect exact retained pip download diagnostics; no environment was installed')
    for path in sorted(wheels.iterdir()):register(path.relative_to(output).as_posix())
    phase('archiving_source')
    subprocess.run(['git','archive','--format=zip','--output',str(output/'source.zip'),head],cwd=ROOT,check=True,timeout=180)
    with zipfile.ZipFile(output/'source.zip') as archive:
        if archive.comment.decode()!=head or archive.testzip() is not None:raise ValueError('Source ZIP identity/CRC mismatch')
        if any('/.local/' in '/'+name or name.startswith('.git/') for name in archive.namelist()):raise ValueError('Private source member')
    register('source.zip')
    for name in ['verify.py','setup_operator.py']:
        copy(ROOT/'release'/name,'scripts/'+name)
    phase('exporting_exact_images')
    with receipt.with_suffix('.save.stderr').open('xb') as err:
        # Preserve repository bindings as well as bytes. Worker attestation
        # requires the independently selected immutable repository reference;
        # an ID-only OCI export has no name to restore on a clean image store.
        subprocess.run(['docker','image','save','--output',str(output/'images.tar'),*sorted({row.get('archive_reference',row['source_reference']) for row in images.values()})],stderr=err,check=True,timeout=240)
    register('images.tar')
    manifest=dict(format='modular-platform-local-kit-1',stage='draft_requires_clean_install_and_G7_closure',source_commit=head,
                  created_utc=datetime.now(timezone.utc).isoformat(),files=state['completed_files'],images=images,
                  trust_boundary='Native/same-origin code is trusted; artifact curation is not executor approval. No control store, credentials, application DB/filestore or worker authority is included.')
    (output/'kit-inventory.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf8')
    sums={name:row['sha256'] for name,row in state['completed_files'].items()};sums['kit-inventory.json']=digest(output/'kit-inventory.json')
    (output/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in sorted(sums.items())),encoding='utf8')
    verify(output)
    phase('draft_verified_requires_operator_and_install_rehearsal')
    report=dict(result=state['phase'],source_commit=head,kit=output.relative_to(ROOT).as_posix(),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files'].values()),
                manifest_sha256=digest(output/'kit-inventory.json'),packages=len(packages),wheels=len(list(wheels.iterdir())),images=images,
                no_existing_control_or_application_data_copied=True,new_Docker_assets=0,limits=['Draft artifact assembly only, not clean-install/OPS03/G7 qualification. Host interpreter archive/wheels are verified data inputs; no global Python installation occurred.'])
    receipt.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
