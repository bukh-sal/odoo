"""Create a project-local Windows operator from verified kit inputs, offline."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,tarfile,venv,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify import verify

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit',type=Path);parser.add_argument('--workdir',type=Path,required=True)
    args=parser.parse_args();kit=args.kit.resolve();manifest=verify(kit)
    work=args.workdir.resolve()
    if work.exists():raise ValueError('Fresh operator workdir required; reconcile any previous attempt first')
    work.mkdir(parents=True,mode=0o700)
    if os.name!='nt':raise RuntimeError('This kit selects the qualified Windows toolchain; no unsupported OS fallback')
    # Only public verified source/toolchain files exist until the SDK is installed.
    # The existing SDK then enforces/validates its OS-owner directory boundary.
    with tarfile.open(kit/'toolchain/python-windows.tar.gz','r:gz') as archive:
        members=archive.getmembers()
        if any(not (m.isfile() or m.isdir()) for m in members):raise ValueError('Unexpected interpreter archive link/type')
        archive.extractall(work/'python',members=members,filter='data')
    executables=list((work/'python').glob('*/python.exe'))
    if len(executables)!=1:raise ValueError('Expected one selected interpreter root')
    base=executables[0];environment=work/'operator'
    subprocess.run([str(base),'-I','-m','venv','--without-pip',str(environment)],check=True,timeout=90)
    selected=environment/'Scripts/python.exe'
    command=[str(base),'-I','-m','pip','--isolated','--disable-pip-version-check','--python',str(selected),'install',
             '--no-index','--find-links',str(kit/'toolchain/wheels'),'--require-hashes','--only-binary=:all:',
             '-r',str(kit/'toolchain/requirements-tooling.lock'),'-r',str(kit/'toolchain/requirements-operator.lock')]
    subprocess.run(command,check=True,timeout=180)
    source=work/'source';source.mkdir()
    with zipfile.ZipFile(kit/'source.zip') as archive:
        if archive.comment.decode()!=manifest['source_commit']:raise ValueError('Source commit differs')
        for info in archive.infolist():
            name=Path(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename:raise ValueError('Invalid source path')
        archive.extractall(source)
    code="import sys;sys.path.insert(0,sys.argv[1]);from modular_platform.operator_os import protect_directory;protect_directory(sys.argv[2]);print('Operator SDK and private OS boundary ready')"
    subprocess.run([str(selected),'-I','-c',code,str(source/'packages/platform_sdk'),str(work)],check=True,timeout=30)
    result=dict(stage='operator_ready_application_not_initialized',source_commit=manifest['source_commit'],python=str(selected),source=str(source))
    (work/'operator-setup.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result))

if __name__=='__main__':main()
