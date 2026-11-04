"""Refresh committed source/bootstrap files in an unsealed local kit, preserving binaries."""
import argparse,json,os,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify import digest,verify

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kit',type=Path);p.add_argument('--receipt',type=Path,required=True);args=p.parse_args()
    kit=args.kit.resolve();old=verify(kit)
    if not kit.is_relative_to(ROOT/'.local/releases') or old['stage']!='draft_requires_clean_install_and_G7_closure':raise ValueError('Owned draft kit required')
    if args.receipt.exists():raise ValueError('Fresh refresh receipt required')
    if subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode:raise ValueError('Commit source before refresh')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    if head==old['source_commit']:raise ValueError('No source update to refresh')
    temporary=kit/'source-refresh.zip';assert not temporary.exists()
    subprocess.run(['git','archive','--format=zip','--output',str(temporary),head],cwd=ROOT,check=True,timeout=180)
    with zipfile.ZipFile(temporary) as archive:
        if archive.comment.decode()!=head or archive.testzip() is not None:raise ValueError('New source snapshot differs')
    assert temporary.resolve().parent==kit and (kit/'source.zip').resolve().parent==kit
    temporary.replace(kit/'source.zip')
    updated=json.loads(json.dumps(old));updated['source_commit']=head
    changed=[]
    for name in ['source.zip','scripts/verify.py','scripts/setup_operator.py']:
        target=kit/name
        if name.startswith('scripts/'):shutil.copyfile(ROOT/'release'/Path(name).name,target)
        row=dict(bytes=target.stat().st_size,sha256=digest(target))
        if row!=old['files'][name]:changed.append(dict(path=name,before=old['files'][name],after=row))
        updated['files'][name]=row
    with (kit/'kit-inventory.json').open('w',encoding='utf8') as f:json.dump(updated,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    sums={name:row['sha256'] for name,row in updated['files'].items()};sums['kit-inventory.json']=digest(kit/'kit-inventory.json')
    (kit/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in sorted(sums.items())),encoding='utf8')
    verify(kit)
    report=dict(result='verified_committed_source_refresh_of_unsealed_kit',source_before=old['source_commit'],source_after=head,changed=changed,
                unchanged_components=sum(row==old['files'][name] for name,row in updated['files'].items()),
                manifest_sha256=digest(kit/'kit-inventory.json'),large_images_plugins_notices_toolchain_reused=True,
                limits=['Draft operator source refresh only; no application deployment, lifecycle mutation or new Docker asset. Kit remains unsealed/unqualified for full G7.'])
    with args.receipt.open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(result=report['result'],changed=len(changed),reused=report['unchanged_components'])))

if __name__=='__main__':main()
