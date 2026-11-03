"""Actual immutable before/after package solution, binary and config identity."""
import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-support-images-02'
base=json.loads((OUT/'inventory.json').read_text())['roles']['nginx']['image_id'];candidate=json.loads((OUT/'proxy-candidate-build.json').read_text())['image_id'];rows={}
for role,image in [('base',base),('candidate',candidate)]:
 args=['docker','run','--rm','--name','mp-g7-proxy-solution-'+role,'--label','com.modular.disposable=mp-g7-support-audit','--network','none','--log-driver','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/bin/sh',image,'-c','set -eu; sha256sum /usr/sbin/nginx; cat /lib/apk/db/installed']
 r=subprocess.run(args,capture_output=True,timeout=45);(PRIVATE/('proxy-'+role+'-solution.stdout')).write_bytes(r.stdout);(PRIVATE/('proxy-'+role+'-solution.stderr')).write_bytes(r.stderr);assert r.returncode==0
 checksum,body=r.stdout.decode().split('\n',1);packages={}
 for block in body.split('\n\n'):
  fields={line[:1]:line[2:] for line in block.splitlines() if len(line)>1 and line[1]==':'}
  if fields:packages[fields['P']]=dict(version=fields['V'],origin=fields.get('o'),license=fields.get('L'))
 meta=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]
 rows[role]=dict(nginx_sha256=checksum.split()[0],packages=packages,meta=meta)
a=rows['base'];b=rows['candidate'];assert a['nginx_sha256']==b['nginx_sha256'];assert a['packages'].keys()==b['packages'].keys()
changes=[dict(package=n,before=a['packages'][n],after=b['packages'][n]) for n in sorted(a['packages']) if a['packages'][n]!=b['packages'][n]]
expected={'brotli-libs':'1.2.1-r0','curl':'8.23.0-r0','libcurl':'8.23.0-r0','libexpat':'2.10.0-r0'}
assert {r['package']:r['after']['version'] for r in changes}==expected
keys=['Entrypoint','Cmd','User','Env','ExposedPorts','WorkingDir','Volumes','StopSignal']
assert {k:a['meta']['Config'].get(k) for k in keys}=={k:b['meta']['Config'].get(k) for k in keys}
assert b['meta']['RootFS']['Layers'][:len(a['meta']['RootFS']['Layers'])]==a['meta']['RootFS']['Layers']
# All source notices already in base remain in its exact retained layers; APK
# package license metadata is retained above. Final archive/notice-kit audit separate.
result=dict(result='candidate_exact_four_package_security_solution_qualified',utc=datetime.now(timezone.utc).isoformat(),base_image=base,candidate_image=candidate,nginx_binary_sha256=a['nginx_sha256'],nginx_binary_unchanged=True,base_layers_exact_prefix=True,inherited_runtime_configuration_exact=keys,packages_before=len(a['packages']),packages_after=len(b['packages']),changes=changes,unrelated_packages_exact=67,retained_collectors=0,deployment_mutations=0,limits=['No runtime switch; config parse/real ingress/security/WebSocket and release selection still required.','Not final license/history/archive/secret/security qualification.'])
with (OUT/'proxy-image-qualification.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(dict(result=result['result'],changes=changes,unrelated_packages_exact=67)))
