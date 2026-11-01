"""Source-only metadata reader qualification; no installation/DB mutation."""
import ast,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
IMAGE='sha256:6eefde4bf3a4abfbb2de75ee64f5347eb6d9dddfba83a55489801aa291a96992'
PROJECT='mp-r0-r1g64bb76636070f'

def command(args,timeout=60):
    value=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=timeout)
    if value.returncode:raise RuntimeError(value.stdout+value.stderr)
    return value

def main():
    results={}
    for name in ['test_external_projection.py','test_projection_tombstones.py','test_planning_cli.py']:
        value=command([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',name])
        results[name]=value.stdout+value.stderr
    freeze=json.loads(command([sys.executable,'-X','utf8','tools/check_contract_freeze.py']).stdout)
    container=command(['docker','ps','-q','--filter','label=com.docker.compose.project='+PROJECT,
        '--filter','label=com.docker.compose.service=app']).stdout.split()
    assert len(container)==1
    assert json.loads(command(['docker','inspect','--format','{{json .Image}}',container[0]],20).stdout)==IMAGE
    modules=['projection','worker_operator']
    sources={name:(ROOT/'packages/platform_sdk/modular_platform'/f'{name}.py').read_text(encoding='utf8') for name in modules}
    test=(ROOT/'tests/test_worker_publication.py').read_text(encoding='utf8')
    # Candidate modules are loaded only in this one test process. The actual
    # installed publisher/OS locks/key reader are unchanged image code. No file
    # in the running release is replaced, and no Odoo registry/DB is opened.
    script='import importlib,json,types,unittest\nsources='+repr(sources)+'\n'
    script+='for name,source in sources.items():\n module=importlib.import_module("modular_platform."+name)\n exec(compile(source,module.__file__,"exec"),module.__dict__)\n'
    script+='test=types.ModuleType("metadata_publication_tests");test.__file__="/opt/modular/tests/test_worker_publication.py"\n'
    script+='exec(compile('+repr(test)+',test.__file__,"exec"),test.__dict__)\n'
    script+='result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test))\nraise SystemExit(0 if result.wasSuccessful() else 1)\n'
    value=subprocess.run(['docker','exec','-i',container[0],'/venv/bin/python','-'],input=script,
        capture_output=True,text=True,encoding='utf8',timeout=90)
    results['linux_publication_source_tests']=value.stdout+value.stderr
    (OUT/'test-results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    if value.returncode:raise RuntimeError('Linux source qualification failed; inspect test-results.json')
    files=['packages/platform_sdk/modular_platform/'+name+'.py' for name in ['projection','deployment','worker_operator']]
    files+=['platform_addons/mp_core/operations.py','tests/test_external_projection.py','tests/test_worker_publication.py']
    for name in files:ast.parse((ROOT/name).read_text(encoding='utf8'))
    report=dict(result='source_readers_passed_not_installed',utc=datetime.now(timezone.utc).isoformat(),
        native_image=IMAGE,tests=dict(external_projection=8,native_tombstones=3,planning_cli=5,linux_publication=13),
        contract_freeze=freeze,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files},
        database_connections=False,release_files_replaced=False,new_images=False,new_volumes=False,
        limitations=['Explicit external reader is not yet wired to lifecycle CLI/independent executor.',
            'Metadata registration, native connector install, final-apply external authority recheck and real remote jobs remain required.',
            'Windows publication run stopped after two passing cases because repeated ACL subprocesses were slow.',
            'One Docker helper-create client stalled before any matching container appeared; stopped without retry or daemon restart.'])
    (OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))

if __name__=='__main__':main()
