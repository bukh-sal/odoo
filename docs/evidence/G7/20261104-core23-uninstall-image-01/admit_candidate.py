"""Actual immutable inventory/source delta and isolated Linux guard checks."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
from modular_platform.release_staging import validate_core_upgrade, core_python_changes

PRIVATE=ROOT/'.local/g7-core23-uninstall-image-01'
assert not PRIVATE.exists();protect_directory(PRIVATE)
build=json.loads((OUT/'candidate-build.json').read_text());assert build['result']=='built_not_deployed'
base_image='sha256:ae8bb33d618305d2d2b000e94e98bf9180e7e8c550e566d0dce0f5c97a2dd73a'
before=inspect_image(base_image);after=inspect_image(build['image_id'])
for name,value in [('base-runtime',before),('candidate-runtime',after)]:
    (PRIVATE/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
source,native=validate_core_upgrade(before,after,dict(base_image_id=base_image,target_image_id=build['image_id']))
expected={'addons/mp_core/__manifest__.py','addons/mp_core/operations.py',
    'packages/contracts/v1/lifecycle-impact.schema.json',
    'packages/contracts/examples/v1/lifecycle-impact/dispatch-base.json',
    'packages/contracts/examples/v1/lifecycle-impact/dispatch-events.json'}
expected|={'packages/platform_sdk/modular_platform/'+name+'.py' for name in
    ['projection','lifecycle_impact','lifecycle_observation','native_executor','native_uninstall','uninstall_planning']}
assert {row['path'] for row in source}==expected
assert native==[dict(addon='mp_core',previous_version='19.0.0.1.22',target_version='19.0.0.1.23',migrations=[])]
assert before['python_metadata']==after['python_metadata'] and len(after['python_metadata'])==77
assert before['python_lock_digest']==after['python_lock_digest']
assert not after['modified_files'] and not after['missing_addon_files'] and not after['unexpected_addon_files']
python_changes=core_python_changes(before,after)
modules={name:(ROOT/'tests'/f'{name}.py').read_text() for name in ['test_native_uninstall','test_lifecycle_contracts']}
helper=(ROOT/'tests/test_plans.py').read_text();tree=ast.parse(helper)
modules['test_plans']='from uuid import UUID\n'+ast.get_source_segment(helper,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ident'))
program='''import json,sys,types,unittest
sources=json.load(sys.stdin);loaded={}
for name in ['test_plans','test_native_uninstall','test_lifecycle_contracts']:
 module=types.ModuleType(name);module.__file__='/opt/modular/tests/'+name+'.py';sys.modules[name]=module
 exec(compile(sources[name],module.__file__,'exec'),module.__dict__);loaded[name]=module
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(loaded[name]) for name in ['test_native_uninstall','test_lifecycle_contracts'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful())))
raise SystemExit(not result.wasSuccessful())
'''
name='mp-g7-core23-offline-guards-01'
command=['docker','run','--rm','-i','--name',name,'--label','mp.disposable=core23-uninstall-guards',
    '--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL',
    '--security-opt','no-new-privileges','--memory','1g','--cpus','2','--tmpfs','/tmp',
    '--entrypoint','/venv/bin/python',build['image_id'],'-B','-c',program]
result=subprocess.run(command,input=json.dumps(modules).encode(),capture_output=True,timeout=90)
(PRIVATE/'linux.stdout').write_bytes(result.stdout);(PRIVATE/'linux.stderr').write_bytes(result.stderr)
assert result.returncode==0,'Inspect private Linux guard diagnostic; do not repeat without correction'
linux=json.loads(result.stdout);assert linux==dict(tests=13,successful=True)
removed=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=30)
assert removed.returncode!=0 and b'no such' in removed.stderr.lower()
report=dict(result='passed_static_candidate_admission',image_id=build['image_id'],inventory_digest=after['inventory_digest'],
    base_image_id=base_image,source_changes=source,native_changes=native,python_dependency_changes=python_changes,
    python_packages=77,python_metadata_and_lock_exact=True,linux=linux,
    test_source_sha256={name:hashlib.sha256(raw.encode()).hexdigest() for name,raw in modules.items()},
    isolated_helper_removed=True,network_config_database_authority_mounts=False,
    limits=['Immutable build/inventory and isolated Linux guard/schema checks only. No installed upgrade, uninstall or recovery acceptance.'])
with (OUT/'candidate-admission.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],image_id=build['image_id'],inventory_digest=after['inventory_digest'],changed_files=len(source),linux=linux)))
