"""Independently inspect built bytes and run offline native primitives."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
from modular_platform.release_staging import validate_core_upgrade,core_python_changes
from modular_platform.resolution import resolve_release
from packaging.utils import canonicalize_name
PRIVATE=ROOT/'.local/g7-core21-dependencies-image-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
built=json.loads((OUT/'candidate-build.json').read_text());assert built['result']=='built_not_deployed'
image=built['image_id'];before_image='sha256:31a673ebbc53fbdecbc5cbfdb5f0eac30d11367630da306d47b5e14cfce17345'
before=inspect_image(before_image);after=inspect_image(image)
for label,value in [('before-runtime',before),('candidate-runtime',after)]:
 (PRIVATE/(label+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
descriptor=dict(base_image_id=before_image,target_image_id=image)
source_changes,native_changes=validate_core_upgrade(before,after,descriptor)
assert native_changes==[dict(addon='mp_core',previous_version='19.0.0.1.20',target_version='19.0.0.1.21',migrations=[])]
assert not after['modified_files'] and not after['unexpected_addon_files'] and not after['missing_addon_files']
review=core_python_changes(before,after)
expected={}
for path in ['deploy/requirements-r1.lock','deploy/build-requirements.lock']:
 for name,version in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s]+)',(ROOT/path).read_text(),re.M):
  name=canonicalize_name(name);assert name not in expected or expected[name]==version;expected[name]=version
actual={canonicalize_name(p['name']):p['version'] for p in after['python_metadata']}
assert actual==expected and len(actual)==76 and 'pypdf2' not in actual
environment=dict(platform_version=after['platform_version'],native_runtime='odoo-19',markers=after['markers'],accepted_wheel_tags=after['accepted_wheel_tags'],core_addons=[])
solution=resolve_release([],after['python_metadata'],environment,{},core_python=[name+'=='+version for name,version in expected.items()])
assert {canonicalize_name(p['name']):p['version'] for p in solution['python']}==expected
fixture=json.loads((ROOT/'packages/contracts/examples/v1/worker-request.json').read_text())
tests=(ROOT/'docs/evidence/G7/20261103-dependency-compatibility-01/native_primitives03.py').read_text()
code='REQUEST='+repr(fixture)+'\n'+tests+"\nsuite=unittest.defaultTestLoader.loadTestsFromTestCase(NativeDependencyCompatibility)\nr=unittest.TextTestRunner(verbosity=2).run(suite)\nprint('MP_CANDIDATE_NATIVE='+json.dumps(dict(tests=r.testsRun,successful=r.wasSuccessful(),failures=[t.id() for t,_ in r.failures],errors=[t.id() for t,_ in r.errors])))\nraise SystemExit(not r.wasSuccessful())\n"
name='mp-g7-core21-offline-native-01'
with (PRIVATE/'native.stdout').open('xb') as out,(PRIVATE/'native.stderr').open('xb') as err:
 r=subprocess.run(['docker','run','--rm','-i','--name',name,'--label','com.modular.disposable=mp-g7-core21-dependencies','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--cpus','2','--tmpfs','/tmp','--entrypoint','/venv/bin/python',image,'-B','-'],input=code.encode(),stdout=out,stderr=err,timeout=120)
rows=[json.loads(line.split('MP_CANDIDATE_NATIVE=',1)[1]) for line in (PRIVATE/'native.stdout').read_text().splitlines() if line.startswith('MP_CANDIDATE_NATIVE=')];assert len(rows)==1
absent=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=30);assert absent.returncode!=0 and b'no such' in absent.stderr.lower()
report=dict(result='passed_static_candidate_admission' if rows[0]['successful'] else 'native_primitive_failed',image_id=image,inventory_digest=after['inventory_digest'],base_image_id=before_image,
 platform_version=after['platform_version'],native_changes=native_changes,source_changes=source_changes,python_dependency_changes=review,
 exact_complete_python_solution=solution['python'],python_packages=76,python_lock_digest=after['python_lock_digest'],native_primitives=rows[0],native_probe_source_sha256=hashlib.sha256(tests.encode()).hexdigest(),
 original_runtime_unchanged=True,temporary_native_helper_removed=True,no_database_config_authority_network_mounts=True,
 limits=['Build, independently observed inventory/dependencies and nine offline native primitive checks only.',
 'Not a running registry/HTTP/session/approval/lifecycle/recovery/security/provenance/fresh-release qualification; current acceptance invalidations remain.'])
with (OUT/'candidate-admission.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],image_id=image,inventory_digest=after['inventory_digest'],python_packages=76,native_primitives=rows[0],dependency_changes=len(review['distributions']))));raise SystemExit(not rows[0]['successful'])
