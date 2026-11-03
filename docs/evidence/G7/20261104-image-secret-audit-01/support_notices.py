"""Preserve shipped PostgreSQL/proxy documentation and notice bytes offline."""
import hashlib,io,json,subprocess,tarfile,zipfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
lock=json.loads((ROOT/'deploy/runtime.lock.json').read_bytes());results={}
code='set --; for p in /usr/share/doc /usr/share/licenses /usr/local/share/licenses /usr/local/share/doc; do if [ -d "$p" ]; then set -- "$@" "$p"; fi; done; test "$#" -gt 0; exec tar -cf - "$@"'
for role,key in [('postgres','postgres_image'),('proxy','reverse_proxy_image')]:
 image=lock[key];path=PRIVATE/(role+'-documentation.tar');assert not path.exists()
 with path.open('xb') as stdout,(PRIVATE/(role+'-documentation.stderr')).open('xb') as stderr:
  result=subprocess.run(['docker','run','--rm','--name','mp-g7-notice-audit-'+role,'--label','com.modular.disposable=mp-g7-notice-audit','--network','none','--log-driver','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--entrypoint','/bin/sh',image,'-c',code],stdout=stdout,stderr=stderr,timeout=60)
 assert result.returncode==0,'Inspect retained archive diagnostics; do not repeat unchanged'
 rows=[];archive=io.BytesIO()
 with tarfile.open(path,'r:*') as source,zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for member in source:
   if not member.isfile():continue
   assert member.size<16*1024*1024
   raw=source.extractfile(member).read();name=member.name.lstrip('/')
   assert '..' not in Path(name).parts
   z.writestr(name,raw);rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 value=archive.getvalue();(PRIVATE/(role+'-documentation.zip')).write_bytes(value)
 absent=subprocess.run(['docker','inspect','--type','container','mp-g7-notice-audit-'+role],capture_output=True,timeout=30);assert absent.returncode and b'no such' in absent.stderr.lower()
 results[role]=dict(image=image,files=rows,archive_sha256=hashlib.sha256(value).hexdigest(),network='none',private_mounts=[],collector_removed=True)
with (OUT/'support-notice-bundles.json').open('x',encoding='utf8') as stream:json.dump(dict(result='preserved_actual_support_image_documentation',roles=results,limits=['Shipped documentation/license bytes preserved; complete per-package license obligations and absent-notice supplement review remain.','Metadata alone is not commercial licensing approval or full OPS03.']),stream,indent=2);stream.write('\n')
print(json.dumps(dict(result='support_notices_preserved',files={k:len(v['files']) for k,v in results.items()})))
