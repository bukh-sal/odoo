"""One bounded offline proxy candidate build from the retained exact APK archive."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-support-images-02'
inputs=json.loads((OUT/'proxy-apk-inputs.json').read_text());raw=(PRIVATE/'proxy-apks.tar').read_bytes();assert hashlib.sha256(raw).hexdigest()==inputs['archive_sha256']
recipe=(ROOT/'deploy/proxy.Dockerfile').read_bytes()
lock=dict(schema_version=1,base='nginx:stable-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951',recipe_sha256=hashlib.sha256(recipe).hexdigest(),pins=inputs['pins'],packages=inputs['packages'],input_archive_sha256=inputs['archive_sha256'],source_evidence='docs/evidence/G7/20261104-support-images-01/proxy-apk-inputs.json',qualification='candidate; signature verification/solution diff/actual ingress review required')
lockpath=ROOT/'deploy/proxy-packages.lock.json';assert not lockpath.exists();lockpath.write_text(json.dumps(lock,indent=2)+'\n')
files={'Dockerfile':recipe,'proxy-packages.lock.json':lockpath.read_bytes()};sums=[]
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for row in inputs['packages']:
  data=archive.extractfile('./'+row['file']).read();assert hashlib.sha256(data).hexdigest()==row['sha256']
  files['apks/'+row['file']]=data;sums.append(row['sha256']+'  '+row['file'])
files['SHA256SUMS']=('\n'.join(sums)+'\n').encode();buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w') as archive:
 for name,data in files.items():
  info=tarfile.TarInfo(name);info.size=len(data);info.mtime=0;info.mode=0o644;archive.addfile(info,io.BytesIO(data))
context=buffer.getvalue();(PRIVATE/'proxy-build-context.tar').write_bytes(context)
tag='modular-platform-proxy:g7-security-20261104-01'
args=['docker','build','--network','none','--pull=false','--label','com.modular.disposable=mp-g7-proxy-candidate','--tag',tag,'-']
with (PRIVATE/'proxy-build.stdout').open('xb') as stdout,(PRIVATE/'proxy-build.stderr').open('xb') as stderr:r=subprocess.run(args,input=context,stdout=stdout,stderr=stderr,timeout=240)
assert r.returncode==0,'Inspect retained exact build logs; do not automatically rebuild'
meta=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]
record=dict(result='offline_proxy_candidate_built_not_deployed',utc=datetime.now(timezone.utc).isoformat(),tag=tag,image_id=meta['Id'],base=lock['base'],build_context_sha256=hashlib.sha256(context).hexdigest(),recipe_sha256=lock['recipe_sha256'],package_lock_sha256=hashlib.sha256(lockpath.read_bytes()).hexdigest(),network='none',APK_hash_verification=True,normal_APK_signatures_required=True,packages=len(inputs['packages']),limits=['Candidate only; exact installed package solution, libraries, ingress/security/notices/layers/secrets remain required.','Original and fresh runtime configurations unchanged; one candidate image retained for qualification.'])
with (OUT/'proxy-candidate-build.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
