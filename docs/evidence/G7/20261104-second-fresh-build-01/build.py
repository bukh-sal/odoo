"""BOOT02: independent no-cache rebuild of the declared core22 target."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.deployment import inspect_image
PRIVATE=ROOT/'.local/g7-second-fresh-build-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
target=json.loads((ROOT/'.local/g7-fresh-release-01/target21/operator/target.json').read_bytes())
assert target['generation']==5
baseline=inspect_image(target['image_id']);assert baseline['platform_version']=='0.1.22'
(PRIVATE/'baseline-runtime.json').write_text(json.dumps(baseline,indent=2)+'\n')
tag='modular-platform:g7-core22-fresh-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%Sz')
command=['docker','build','--no-cache','-f','deploy/Dockerfile','--build-arg','DISTRIBUTION_POLICY=deploy/distribution-r1-notes-stats.json','--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',tag,'.']
source={}
for directory in ['platform_addons','plugins','packages/contracts','packages/platform_sdk','deploy','tools']:
 for path in sorted((ROOT/directory).rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':source[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
for name in ['.dockerignore','LICENSE','COPYRIGHT']:source[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
record=dict(state='building',tag=tag,command=command,baseline_image=target['image_id'],baseline_inventory=baseline['inventory_digest'],source_head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),source_sha256=source)
(PRIVATE/'state.json').write_text(json.dumps(record,indent=2)+'\n')
started=time.monotonic();print(json.dumps(dict(state='no_cache_second_build_started',tag=tag)),flush=True)
with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
 with (OUT/'build.log').open('xb') as stream:r=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
 assert r.returncode==0,'Inspect retained exact build; do not rerun unchanged'
 image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
 actual=inspect_image(image)
for name,digest in source.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'Build input changed'
assert actual['inventory']==baseline['inventory'] and actual['inventory_digest']==baseline['inventory_digest']
assert actual['python_lock_digest']==baseline['python_lock_digest'] and actual['platform_version']==baseline['platform_version']
def packages(value):return {p['name']:p['version'] for p in value['python_metadata']}
assert packages(actual)==packages(baseline)
(PRIVATE/'rebuilt-runtime.json').write_text(json.dumps(actual,indent=2)+'\n')
report=record|dict(result='passed_second_fresh_no_cache_declared_inventory',state='qualified',image_id=image,inventory_digest=actual['inventory_digest'],inventory_exact=True,python_lock_exact=True,Python_distribution_versions_exact=True,python_distributions=len(actual['python_metadata']),declared_source_files=len(actual['inventory']['files']),native_addons=len(actual['inventory']['native_addons']),elapsed_seconds=round(time.monotonic()-started,3),deployment_changed=False,limits=['No-cache build reproduces complete declared source/plugin/addon/artifact inventory and dependency versions; not a claim of byte-identical image layers or native compiler timestamps.','Fresh reference installation/upgrade/recovery evidence remains separately linked; no new database or application fixture created here.','Rebuilt image is a disposable qualification artifact pending exact cleanup, not an approved replacement runtime.'])
(OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');(PRIVATE/'state.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['result','image_id','inventory_digest','python_distributions','elapsed_seconds']}),flush=True)
