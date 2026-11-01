"""Pure planning/independent review and real Linux OS-reader source checks."""
import ast,hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
IMAGE='sha256:6eefde4bf3a4abfbb2de75ee64f5347eb6d9dddfba83a55489801aa291a96992'
PROJECT='mp-r0-r1g64bb76636070f'

def run(args,**kwargs):
    return subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90,**kwargs)

def main():
    results={};counts={}
    suites=['external_planning','external_projection','projection_tombstones','planning_cli',
        'lifecycle_planning','reinstall_planning','uninstall_planning','manager_planning']
    for suite in suites:
        value=run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_'+suite+'.py'])
        results[suite]=value.stdout+value.stderr
        (OUT/'test-results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
        if value.returncode:raise RuntimeError('Source suite failed: '+suite)
        counts[suite]=int(re.search(r'Ran (\d+) tests?',results[suite])[1])
    containers=run(['docker','ps','-q','--filter','label=com.docker.compose.project='+PROJECT,'--filter','label=com.docker.compose.service=app'])
    assert containers.returncode==0 and len(containers.stdout.split())==1
    container=containers.stdout.strip()
    identity=run(['docker','inspect','--format','{{json .Image}}',container])
    assert identity.returncode==0 and json.loads(identity.stdout)==IMAGE
    sources={name:(ROOT/'packages/platform_sdk/modular_platform'/f'{name}.py').read_text(encoding='utf8') for name in ['projection','deployment','worker_operator']}
    test=(ROOT/'tests/test_worker_publication.py').read_text(encoding='utf8')
    script='import importlib,types,unittest\nsources='+repr(sources)+'\n'
    script+='for name,source in sources.items():\n module=importlib.import_module("modular_platform."+name)\n exec(compile(source,module.__file__,"exec"),module.__dict__)\n'
    script+='test=types.ModuleType("candidate_tests");test.__file__="/opt/modular/tests/test_worker_publication.py"\n'
    script+='exec(compile('+repr(test)+',test.__file__,"exec"),test.__dict__)\n'
    script+='result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test))\nraise SystemExit(0 if result.wasSuccessful() else 1)\n'
    value=run(['docker','exec','-i',container,'/venv/bin/python','-'],input=script)
    results['linux_publication']=value.stdout+value.stderr
    (OUT/'test-results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    if value.returncode:raise RuntimeError('Linux OS source suite failed')
    counts['linux_publication']=int(re.search(r'Ran (\d+) tests?',results['linux_publication'])[1])
    value=run([sys.executable,'-X','utf8','tools/check_contract_freeze.py']);assert value.returncode==0
    freeze=json.loads(value.stdout)
    files=['packages/platform_sdk/modular_platform/'+name+'.py' for name in ['external_planning','projection','deployment','worker_operator','approval_validation','native_executor']]
    files+=['tools/modular.py','tests/test_external_planning.py','tests/test_worker_publication.py','tests/test_reinstall_planning.py','tests/test_uninstall_planning.py']
    for name in files:ast.parse((ROOT/name).read_text(encoding='utf8'))
    report=dict(result='metadata_planning_review_source_passed_not_installed',utc=datetime.now(timezone.utc).isoformat(),
        tests=counts,total_tests=sum(counts.values()),contract_freeze=freeze,
        sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files},
        linux_profile=dict(image=IMAGE,isolated_source_process=True,installed_code_replaced=False,database_connections=False),
        metadata_registered=False,new_containers=False,new_images=False,new_volumes=False,
        corrections=['Current-archive reinstall fixture used legacy platform0.1.0; aligned both staged images with its already current environment/core.',
            'Uninstall post-observation fixture used legacy global provenance; use the actual matching document provenance.',
            'Linux source harness initially omitted the candidate deployment reader; now loads its exact source before worker composition tests.',
            'Optional unregister initially made unchanged published service choices unobservable; preserve OS-pinned external choices without recreating live bindings.'],
        limitations=['No metadata execution/drain/recovery or actual endpoint activation yet.',
            'Upgrade version test uses a synthetic second catalog descriptor; no actual upgraded worker/artifact qualification.',
            'Independent validator source tests substitute catalog/observation IO; actual protected publisher and composition-root files tested separately on Linux.',
            'Native executor deliberately refuses external artifacts before drain until managed-worker adapter is implemented.'])
    (OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))

if __name__=='__main__':main()
