"""Real worker engine/process tests against immutable candidate source bytes."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-worker-dependencies-image-01'
build=json.loads((OUT/'candidate-build.json').read_text());assert build['state']=='built_not_started_not_approved'
names=['tests/test_document_stats_engine.py','tests/test_document_stats_process.py','packages/contracts/examples/v1/worker-request.json']
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w') as tar:
 for name in names:tar.add(ROOT/name,arcname=name,recursive=False)
 info=tarfile.TarInfo('tests/__init__.py');info.size=0;tar.addfile(info,io.BytesIO(b''))
code="""import json,pathlib,sys,tarfile,unittest
root=pathlib.Path('/tmp/worker-tests');root.mkdir()
tar=tarfile.open(fileobj=sys.stdin.buffer,mode='r|')
for member in tar:tar.extract(member,path=root,filter='data')
# Process tests use an isolated cwd; link only to actual immutable image code.
(root/'services').symlink_to('/app/services',target_is_directory=True)
(root/'packages/platform_sdk').symlink_to('/app/packages/platform_sdk',target_is_directory=True)
sys.path.insert(0,str(root))
from tests.test_document_stats_engine import WorkerEngineTests
from tests.test_document_stats_process import WorkerProcessTests
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(WorkerEngineTests),unittest.defaultTestLoader.loadTestsFromTestCase(WorkerProcessTests)])
r=unittest.TextTestRunner(verbosity=2).run(suite)
print('MP_WORKER_IMAGE_TESTS='+json.dumps(dict(tests=r.testsRun,successful=r.wasSuccessful(),failures=[t.id() for t,_ in r.failures],errors=[t.id() for t,_ in r.errors])))
raise SystemExit(not r.wasSuccessful())
"""
name='mp-g7-worker-security-tests-01'
with (PRIVATE/'tests.stdout').open('xb') as out,(PRIVATE/'tests.stderr').open('xb') as err:
 r=subprocess.run(['docker','run','--rm','-i','--name',name,'--label','com.modular.disposable=mp-g7-worker-security','--log-driver','none','--network','none','--read-only','--user','10002:10002','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--cpus','2','--pids-limit','128','--tmpfs','/tmp','--entrypoint','/venv/bin/python',build['image_id'],'-B','-c',code],input=archive.getvalue(),stdout=out,stderr=err,timeout=180)
rows=[json.loads(line.split('MP_WORKER_IMAGE_TESTS=',1)[1]) for line in (PRIVATE/'tests.stdout').read_text().splitlines() if line.startswith('MP_WORKER_IMAGE_TESTS=')];assert len(rows)==1
gone=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=30);assert gone.returncode!=0 and b'no such' in gone.stderr.lower()
report=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],image_id=build['image_id'],source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names},actual_immutable_worker_code=True,ephemeral_fixture_keys_only=True,no_network_config_db_issuer_operator_mounts=True,temporary_container_removed=True,
 limits=['Real isolated engine/HTTP process compatibility tests, not an approved active endpoint/runtime transition or final security/recovery qualification.'])
with (OUT/'image-tests.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(rows[0]));raise SystemExit(not rows[0]['successful'])
