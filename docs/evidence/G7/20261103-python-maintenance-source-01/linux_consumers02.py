"""Run changed planning consumers on Linux in the existing candidate VENV.

No build/install/database/original source mount; source is a bounded stdin tar.
The sole existing probe volume is read-only and the terminal helper is --rm.
"""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-dependency-compatibility-01'
state=json.loads((PRIVATE/'probe-state.json').read_text());assert state['state']=='primitive_compatibility_qualified_helpers_retired_probe_retained'
paths=[]
for directory in ['packages/platform_sdk','packages/contracts','tests','tools','plugins','platform_addons']:
 paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and not any(n in p.parts for n in ['__pycache__','node_modules','.git']) and p.suffix!='.pyc')
paths.extend(ROOT/n for n in ['LICENSE','COPYRIGHT'])
sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w:gz') as tar:
 for p in sorted(paths):tar.add(p,arcname=p.relative_to(ROOT).as_posix(),recursive=False)
code="""import json,pathlib,sys,tarfile,unittest
root=pathlib.Path('/tmp/source');root.mkdir()
tar=tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz')
for member in tar:tar.extract(member,path=root,filter='data')
sys.path[:0]=[str(root/'tests'),str(root/'tools'),str(root/'packages/platform_sdk')]
names=['core_python_maintenance','core_upgrade','release_staging','platform_deploy','resolution','plans','planning_cli']
suite=unittest.TestSuite(unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_'+name+'.py') for name in names)
result=unittest.TextTestRunner(verbosity=2).run(suite)
print('MP_LINUX_CONSUMERS='+json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),failures=[test.id() for test,_ in result.failures],errors=[test.id() for test,_ in result.errors])))
raise SystemExit(not result.wasSuccessful())
"""
name=state['project']+'-source-linux-02'
args=['docker','run','--rm','-i','--name',name,'--label','com.modular.disposable='+state['project'],'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--cpus','2','--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--mount','type=volume,source='+state['volume']+',target=/probe,readonly','--entrypoint','/probe/venv/bin/python',state['image'],'-B','-c',code]
with (PRIVATE/'source-linux-02.stdout').open('xb') as out,(PRIVATE/'source-linux-02.stderr').open('xb') as err:
 result=subprocess.run(args,input=archive.getvalue(),stdout=out,stderr=err,timeout=120)
raw=(PRIVATE/'source-linux-02.stdout').read_text();rows=[json.loads(line.split('MP_LINUX_CONSUMERS=',1)[1]) for line in raw.splitlines() if line.startswith('MP_LINUX_CONSUMERS=')]
assert len(rows)==1,'Inspect exact helper outcome before any continuation'
report=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],base_image=state['image'],readonly_probe_volume=state['volume'],source_sha256=sources,source_archive_sha256=hashlib.sha256(archive.getvalue()).hexdigest(),
 no_network_database_config_issuer_original_source_mounts=True,qualified_runtime_unchanged=True,
 limits=['Source consumers under candidate dependencies only; not a built release or deployed registry/lifecycle/security pass.'])
absent=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=30)
assert absent.returncode!=0 and b'no such' in absent.stderr.lower();report['temporary_helper_removed']=True
with (OUT/'linux-consumers02.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(rows[0]));raise SystemExit(not rows[0]['successful'])
