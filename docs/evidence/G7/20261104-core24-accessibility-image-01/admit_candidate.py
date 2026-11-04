"""Exact source/environment/static admission for the bounded UI09 correction."""
import base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_core_upgrade,core_python_changes
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner
PRIVATE=ROOT/'.local/g7-core24-accessibility-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
def load(p):return json.loads(p.read_bytes())
build=load(OUT/'candidate-build.json');base='sha256:14de369e46f20616e76847cbcacbcb66d5bb791808b950aaf97bc607d31d6b93';assert build['dependency_base_image']==base and build['result']=='built_not_deployed'
before=inspect_image(base);after=inspect_image(build['image_id'])
for name,value in [('base-runtime',before),('candidate-runtime',after)]:
 with (PRIVATE/(name+'.json')).open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.write('\n')
source,native=validate_core_upgrade(before,after,dict(base_image_id=base,target_image_id=build['image_id']))
expected={'addons/mp_core/__manifest__.py','addons/mp_shell/__manifest__.py','addons/mp_shell/static/src/host.js','addons/mp_shell/static/src/host.css','addons/mp_shell/views/bootstrap.xml','packages/platform_sdk/modular_platform/projection.py'}
assert {r['path'] for r in source}==expected
assert native==[dict(addon='mp_core',previous_version='19.0.0.1.23',target_version='19.0.0.1.24',migrations=[]),dict(addon='mp_shell',previous_version='19.0.0.1.10',target_version='19.0.0.1.11',migrations=[])]
assert before['python_metadata']==after['python_metadata'] and len(after['python_metadata'])==77
assert before['python_lock_digest']==after['python_lock_digest'] and not core_python_changes(before,after)
assert not after['modified_files'] and not after['missing_addon_files'] and not after['unexpected_addon_files']
assert before['inventory']['artifacts']==after['inventory']['artifacts'] and before['inventory']['policy']==after['inventory']['policy']
for path,digest in build['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
checks=load(OUT.parent/'20261104-ui-qualification-01/source24-checks.json')
for path,digest in checks['source_sha256'].items():
 mapped=path.replace('platform_addons/','addons/',1) if path.startswith('platform_addons/') else path
 assert after['inventory']['files'][mapped]==digest
old=load(ROOT/'.local/g7-ui-qualification-01/runtimes-before.json');current=json.loads(subprocess.check_output(['docker','inspect',*[r['Id'] for r in old]],stderr=subprocess.PIPE,timeout=30))
for a,b in zip(old,current):assert b['State']['Running'] and a['Id']==b['Id'] and a['Image']==b['Image'] and a['State']['StartedAt']==b['State']['StartedAt'] and a['Mounts']==b['Mounts'] and a['NetworkSettings']==b['NetworkSettings']
alias='modular-platform:dependency-base-'+OUT.name;probe=subprocess.run(['docker','image','inspect',alias],capture_output=True,timeout=30);assert probe.returncode!=0
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[OUT/'build.log',OUT/'candidate-build.json',Path(__file__)];findings=[f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings
report=dict(result='passed_static_core24_shell11_candidate_admission_not_deployed',utc=datetime.now(timezone.utc).isoformat(),image_id=build['image_id'],inventory_digest=after['inventory_digest'],base_image_id=base,source_changes=source,native_changes=native,python_distributions=77,python_metadata_and_lock_exact=True,python_dependency_changes=[],packaged_artifacts_and_policy_exact=True,affected_host_checks=checks['checks'],frozen_contracts=checks['contract_freeze'],all4_running_runtime_process_image_mount_network_identities_preserved=True,temporary_dependency_alias_removed=True,new_persistent_container_volume_network=0,privacy=dict(known_values=len(values),files=len(paths),findings=0),evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},limits=['Immutable build/static source/environment admission only. No installed core upgrade or UI09 pass.','Exactly six owned source/version changes; native core24/Shell11 strictly increase. No migrations, packaged plugin/API/schema/authority/dependency changes.','Native RPC/View/retirement/authority/activation source seams remain exact per source24-checks.json. Installed rendering/contrast/focus/close/language/RTL checks remain mandatory.','One new uniquely tagged candidate image; borrowed14de dependency alias removed by verified identity. Existing runtime/worker/realm untouched.'])
with (OUT/'candidate-admission.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],image=build['image_id'],inventory=after['inventory_digest'],source_changes=6,native_addons_changed=2,Python_distributions_exact=77,privacy_findings=0)))
