"""Fetch exact public signed APK inputs in an isolated disposable helper."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-support-images-02'
image=json.loads((OUT/'inventory.json').read_text())['roles']['nginx']['image_id']
pins=['brotli-libs=1.2.1-r0','curl=8.23.0-r0','libcurl=8.23.0-r0','libexpat=2.10.0-r0']
script='set -eu; mkdir /tmp/apks; apk fetch --no-cache --recursive --output /tmp/apks "$@" >&2; tar -C /tmp/apks -cf - .'
args=['docker','run','--rm','--name','mp-g7-proxy-apk-fetch-01','--label','com.modular.disposable=mp-g7-support-audit','--read-only','--log-driver','none','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--tmpfs','/var/cache/apk:rw,nosuid,nodev,noexec,size=32m','--entrypoint','/bin/sh',image,'-c',script,'fetch',*pins]
with (PRIVATE/'proxy-apks.tar').open('xb') as output,(PRIVATE/'proxy-apks-fetch.stderr').open('xb') as error:r=subprocess.run(args,stdout=output,stderr=error,timeout=120)
assert r.returncode==0,'Inspect retained fetch error before changing pins or retrying'
raw=(PRIVATE/'proxy-apks.tar').read_bytes();rows=[]
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for member in archive.getmembers():
  if not member.isfile():continue
  name=member.name.removeprefix('./');assert '/' not in name and name.endswith('.apk')
  data=archive.extractfile(member).read();rows.append(dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
record=dict(result='exact_proxy_APK_inputs_fetched_candidate_not_built',utc=datetime.now(timezone.utc).isoformat(),base_image=image,pins=pins,archive_sha256=hashlib.sha256(raw).hexdigest(),packages=sorted(rows,key=lambda r:r['file']),helper_removed=True,mounts=[],private_inputs='proxy-apks.tar',limits=['Download staging only. Offline image APK signature verification, exact solution diff, notices and actual ingress behavior still required.','No deployment/image/config/key mutation or public contract change.'])
with (OUT/'proxy-apk-inputs.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],packages=len(rows),bytes=len(raw))))
