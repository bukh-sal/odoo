"""Actual support-image identities/package inventory, disposable offline collectors only."""
import hashlib,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-support-images-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
state=json.loads((ROOT/'.local/g7-fresh-release-01/target21/state.json').read_text());project=state['project'];lock=json.loads((ROOT/'deploy/runtime.lock.json').read_text())
def run(label,args):
 r=subprocess.run(args,capture_output=True,timeout=60)
 (PRIVATE/(label+'.stdout')).write_bytes(r.stdout);(PRIVATE/(label+'.stderr')).write_bytes(r.stderr)
 assert r.returncode==0,'Inspect retained exact helper diagnostics before continuing'
 return r.stdout
def helper(role,image,entry,args):
 return run(role+'-'+entry.replace('/','_'),['docker','run','--rm','--name','mp-g7-support-audit-'+role+'-'+entry.split('/')[-1], '--label','com.modular.disposable=mp-g7-support-audit','--network','none','--log-driver','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--entrypoint',entry,image,*args])
rows={}
for role,suffix,pin in [('postgres','db','postgres_image'),('nginx','edge','reverse_proxy_image')]:
 image=run(role+'-identity',['docker','inspect','--format','{{.Image}}',project+'-'+suffix+'-1']).decode().strip()
 meta=json.loads(run(role+'-metadata',['docker','image','inspect','--format','{{json .}}',image]))
 assert lock[pin] in meta['RepoDigests'],(role,'pinned image differs')
 row=dict(image_id=image,pinned_reference=lock[pin],architecture=meta['Architecture'],OS=meta['Os'],rootfs_layers=meta['RootFS']['Layers'])
 if role=='postgres':
  version=helper(role,image,'postgres',['--version']).decode().strip()
  raw=helper(role,image,'dpkg-query',['-W','-f=${Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\n'])
  packages=[]
  for line in raw.decode().splitlines():
   name,version_,arch,source,srcversion=line.split('\t');packages.append(dict(name=name,version=version_,architecture=arch,source_package=source,source_version=srcversion))
  row.update(version=version,packages=packages)
 else:
  raw=helper(role,image,'/bin/sh',['-c','nginx -V 2>&1; printf "\nALPINE_RELEASE\n"; cat /etc/alpine-release; printf "\nPACKAGES\n"; cat /lib/apk/db/installed'])
  head,body=raw.decode().split('\nPACKAGES\n');build,release=head.split('\nALPINE_RELEASE\n');packages=[]
  for block in body.split('\n\n'):
   fields={line[:1]:line[2:] for line in block.splitlines() if len(line)>1 and line[1]==':'}
   if fields:packages.append(dict(name=fields['P'],version=fields['V'],origin=fields.get('o'),license=fields.get('L'),architecture=fields.get('A'),source_commit=fields.get('c'),description=fields.get('T')))
  row.update(version_and_build=build,alpine_release=release.strip(),packages=packages)
 rows[role]=row
record=dict(result='actual_pinned_support_images_collected_review_pending',utc=datetime.now(timezone.utc).isoformat(),roles=rows,images_built=0,deployment_mutations=0,retained_collectors=0,limits=['Static metadata/package identities, not a full advisory/license/network/history/secret qualification.','Exact current database/proxy images; no database/config/userdata mounts or runtime restarts.'])
with (OUT/'inventory.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps({role:dict(image=r['image_id'],packages=len(r['packages']),version=r.get('version',r.get('alpine_release'))) for role,r in rows.items()}))
