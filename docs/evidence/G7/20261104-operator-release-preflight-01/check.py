"""Read-only current/kit operator compatibility; never refresh or apply a release."""
import base64, hashlib, json, re, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path.cwd(); OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'release')]
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner
from verify import verify

PRIVATE=ROOT/'.local/g7-operator-release-preflight-01'
assert PRIVATE.is_dir() and not (OUT/'qualification.json').exists()
assert (OUT/'check01.py').is_file()
ref=ROOT/'.local/release-kit-rehearsal/private/reference/operator'
kit=ROOT/'.local/releases/r1-0.1.23'
python=ROOT/'.local/release-kit-rehearsal/operator/Scripts/python.exe'
operation='04fa2cfb-b2d1-4ae3-b251-75b9c931630a'
def sha(data): return hashlib.sha256(data).hexdigest()
def load(path): return json.loads(path.read_bytes())
def tree(path): return {p.relative_to(path).as_posix():sha(p.read_bytes()) for p in path.rglob('*') if p.is_file()}
def run(label,args):
    if (PRIVATE/(label+'.stdout')).is_file():
        stdout=(PRIVATE/(label+'.stdout')).read_bytes();stderr=(PRIVATE/(label+'.stderr')).read_bytes()
        if label.endswith('.py'): assert b'\nOK\r\n' in stderr or b'\nOK\n' in stderr
        else: json.loads(stdout);assert not stderr
        return subprocess.CompletedProcess(args,0,stdout,stderr)
    result=subprocess.run(args,capture_output=True,timeout=90)
    for ext,data in [('stdout',result.stdout),('stderr',result.stderr)]:
        with (PRIVATE/(label+'.'+ext)).open('xb') as f:f.write(data)
    assert result.returncode==0,label+' failed; inspect private streams, no replay'
    return result
target=load(ref/'target.json'); assert target['generation']==5
before=tree(ref/'control')
ids=[target['worker_id'],target['project']+'-db-1',target['project']+'-edge-1',
     '4daa036c0e3a871ec20c95de8a4784f9432fbf3bd131bb31eb5d7839181af9f8']
def runtimes():
    rows=json.loads(subprocess.check_output(['docker','inspect',*ids],stderr=subprocess.PIPE,timeout=30))
    return [dict(id=r['Id'],image=r['Image'],state={k:r['State'][k] for k in ['Status','Running','Pid','StartedAt','Restarting']},
                 mounts=r['Mounts'],networks=r['NetworkSettings']['Networks']) for r in rows]
runtime_before=runtimes()
manifest=verify(kit)
with zipfile.ZipFile(kit/'source.zip') as archive:
    assert archive.comment.decode()==manifest['source_commit']
    current=subprocess.check_output(['git','ls-files','tools','packages','release','deploy','platform_addons']).decode().splitlines()
    names=set(archive.namelist()); changed=[]
    for path in current:
        old=archive.read(path) if path in names else None; new=(ROOT/path).read_bytes()
        if old!=new: changed.append(dict(path=path,kit_sha256=sha(old) if old is not None else None,current_sha256=sha(new)))
expected={'packages/platform_sdk/modular_platform/projection.py','platform_addons/mp_core/__manifest__.py',
          'platform_addons/mp_shell/__manifest__.py','platform_addons/mp_shell/static/src/host.css',
          'platform_addons/mp_shell/static/src/host.js','platform_addons/mp_shell/views/bootstrap.xml',
          'tools/modular.py','tools/operation_progress.py'}
assert {r['path'] for r in changed}==expected
commands=[('current',ROOT/'tools/modular.py'),('kit',ROOT/'.local/release-kit-rehearsal/source/tools/modular.py')]
shows={}
for label,script in commands:
    result=run(label+'-show',[str(python),'-I',str(script),'--config',str(ref/'trust.json'),
               'operations','--store',str(ref/'control'),'show',operation])
    shows[label]=json.loads(result.stdout)
assert 'executor_observation' not in shows['kit']
observation=shows['current'].pop('executor_observation')
assert observation['state']=='returned' and shows['current']==shows['kit']
assert shows['current']['state']=='completed' and shows['current']['traffic_resumed']
tests=[]
for pattern in ['test_operation_progress.py','test_metadata_executor.py','test_executor_crash_fence.py']:
    result=run(pattern,[str(python),'-I','-m','unittest','discover','-s','tests','-p',pattern,'-v'])
    match=re.search(rb'Ran (\d+) tests?',result.stderr);assert match
    tests.append(dict(pattern=pattern,tests=int(match[1]),exit_code=0,stream_sha256=sha(result.stdout+result.stderr)))
assert before==tree(ref/'control'), 'Read-only operator changed durable control contents'
assert runtime_before==runtimes(), 'Runtime identity or state changed'
values={k:base64.b64decode(v) for k,v in load(ref.parent/'qualification-known-values-worker.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
assert not [finding for path in [*PRIVATE.iterdir(),Path(__file__),OUT/'check01.py']
            for finding in scanner.inspect_file(path,str(path.relative_to(ROOT)))]
receipt=dict(result='passed_current_operator_on_kit_environment_with_explicit_source_gap',utc=datetime.now(timezone.utc).isoformat(),
    source_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),kit_source_commit=manifest['source_commit'],
    kit_components_verified=len(manifest['files']),code_delta=changed,tests=tests,
    current_completed_operation_readback=True,kit_legacy_journal_fields_exact=True,
    current_observation_state=observation['state'],durable_control_files_exact=len(before),four_runtimes_exact=True,
    initial_attempt='check01 completed both live readbacks and all tests; final full-State comparison included changing Docker health-check timestamps. Corrected stable identity comparison; exact existing command/test streams reused, no replay.',
    privacy=dict(known_values=len(values),findings=0),
    limits=['Existing kit source lacks the independent CLI observation addition; current source works with its separately installed operator environment.',
            'Kit remains draft and still packages old14de image. No source refresh, image export, release seal or OPS03/BOOT02/UI09 pass.',
            'No lifecycle operation, database query/write, browser, new Docker asset or cleanup was executed.',
            'Tests use isolated temporary stores; completed live operation is only read, never replayed.'])
for name in ['docs/operator-runbooks.md','tools/modular.py','tools/operation_progress.py']:
    receipt.setdefault('current_source_sha256',{})[name]=sha((ROOT/name).read_bytes())
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(dict(result=receipt['result'],tests=sum(t['tests'] for t in tests),code_delta=len(changed),privacy_findings=0)))
