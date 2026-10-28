"""Fixed child: select one checkpoint site into a fresh filestore directory."""
import json
from pathlib import Path,PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile


def restore(stream,root,original,target):
    if (original==target or any(not isinstance(name,str) or len(name)>63
            or not re.fullmatch(r'mp_disposable_r0_r1_[a-z0-9_]+',name) for name in (original,target))):
        raise ValueError('Distinct canonical disposable source/restore database identities required')
    root=Path(root).absolute();destination=root/target
    if destination.exists() or destination.is_symlink():
        raise ValueError('Never overwrite an existing restore filestore')
    for path in (root,*root.parents):
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():
            raise ValueError('Restore target cannot traverse links or junctions')
    selected,ignored,seen=0,0,set()
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(fileobj=stream,mode='r|gz') as archive:
            for member in archive:
                name=member.name[:-1] if member.isdir() and member.name.endswith('/') else member.name
                path=PurePosixPath(name)
                if (not (member.isdir() or member.isfile()) or path.is_absolute() or '\\' in name or '\x00' in name
                        or not path.parts or path.parts[0]!='filestore' or any(part in ('','.','..') for part in name.split('/'))
                        or path.as_posix()!=name or len(path.parts)<=2 and not member.isdir()):
                    raise ValueError('Unsafe checkpoint archive member')
                if len(path.parts)==1 or path.parts[1]!=original:
                    ignored+=1
                    continue
                key=name.casefold()
                if key in seen:raise ValueError('Duplicate checkpoint member')
                seen.add(key)
                archive.extract(member,temporary,filter='data')
                selected+=int(member.isfile())
        source=Path(temporary)/'filestore'/original
        root.mkdir(parents=True,exist_ok=True)
        if source.exists():shutil.copytree(source,destination)
        else:destination.mkdir()
    return {'filestore_restored':True,'selected_files':selected,'ignored_members':ignored}


if __name__=='__main__':
    original,target=sys.argv[1:3]
    root=sys.argv[3] if len(sys.argv)==4 else '/var/lib/modular/filestore'
    print(json.dumps(restore(sys.stdin.buffer,root,original,target)))
