"""Run only in the trusted read-only operator archive helper; no Odoo imports."""
import gzip,hashlib,json,os,stat,sys,tarfile
from pathlib import Path
ROOT=Path('/source')
def inventory():
 result={}
 def visit(path,name):
  info=path.lstat();entry=dict(uid=info.st_uid,gid=info.st_gid,mode=stat.S_IMODE(info.st_mode),mtime_ns=info.st_mtime_ns)
  if stat.S_ISDIR(info.st_mode):
   entry['kind']='directory';result[name]=entry
   for child in sorted(path.iterdir(),key=lambda p:p.name):visit(child,name+'/'+child.name)
  elif stat.S_ISREG(info.st_mode):
   digest=hashlib.sha256();size=0
   with path.open('rb') as stream:
    while chunk:=stream.read(1024*1024):digest.update(chunk);size+=len(chunk)
   assert size==info.st_size
   result[name]=dict(entry,kind='file',size=size,sha256=digest.hexdigest())
  elif stat.S_ISLNK(info.st_mode):result[name]=dict(entry,kind='symlink',target=os.readlink(path))
  else:raise RuntimeError('Unsupported special file; preserve source volume for separate assessment')
 visit(ROOT,'volume');return result
before=inventory()
with gzip.GzipFile(fileobj=sys.stdout.buffer,mode='wb',compresslevel=1,mtime=0,filename='') as compressed:
 with tarfile.open(fileobj=compressed,mode='w|',dereference=False) as archive:archive.add(ROOT,arcname='volume',recursive=True)
assert inventory()==before,'Source changed; preserve volume, reject this archive'
print('MP_VOLUME_ARCHIVE='+json.dumps(dict(manifest=before,regular_file_bytes=sum(v.get('size',0) for v in before.values()))),file=sys.stderr,flush=True)
