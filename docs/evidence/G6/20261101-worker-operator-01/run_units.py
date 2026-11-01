"""Current publisher/bootstrap source on the real Linux OS/file/lock substrate."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
private=ROOT/'.local/document-stats/operator-05';native=json.loads((ROOT/'.local/g6-events/state.json').read_text())
code="import sys,types,json,unittest\nsys.path.insert(0,'/opt/modular/packages/platform_sdk')\n"
sources=['packages/platform_sdk/modular_platform/worker_publication.py','packages/platform_sdk/modular_platform/worker_projection.py','packages/platform_sdk/modular_platform/worker_authority.py','tests/test_worker_publication.py']
for path in sources[:-1]:
    module='modular_platform.'+Path(path).stem
    code+='m=types.ModuleType('+repr(module)+');m.__package__="modular_platform";sys.modules[m.__name__]=m\nexec(compile('+repr((ROOT/path).read_text())+",'current_operator_source','exec'),m.__dict__)\n"
code+="scope={'__name__':'publication_tests','__file__':'/opt/modular/tests/test_worker_publication.py'}\nexec(compile("+repr((ROOT/sources[-1]).read_text())+",'current_operator_tests','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['WorkerPublicationTests']))\nprint(json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures])))\nraise SystemExit(0 if result.wasSuccessful() else 1)"
stdout=private/'linux-units.stdout';stderr=private/'linux-units.stderr';assert not stdout.exists()
with stdout.open('xb') as out,stderr.open('xb') as err:
    result=subprocess.run(['docker','run','--rm','-i','--name','mp-disposable-worker-operator-units','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,uid=10001,gid=10001','--entrypoint','/venv/bin/python',native['image_id'],'-c','import sys;exec(compile(sys.stdin.read(),"current_unit_source","exec"))'],input=code.encode(),stdout=out,stderr=err,timeout=45)
record=json.loads(stdout.read_bytes());record.update(source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in sources},helper_auto_removed=True,no_volumes_or_images_created=True,runtime_observations='Explicit fixture data; real OS owner/keys/files/locks')
(OUT/'linux-units.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(tests=record['tests'],successful=record['successful'])));raise SystemExit(result.returncode)
