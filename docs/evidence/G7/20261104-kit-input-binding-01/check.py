"""Verify actual old receipt refusal; never assemble/refresh an existing kit."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(ROOT/'release')]
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner
from verify import verify

PRIVATE=ROOT/'.local/g7-kit-input-binding-01'
assert not PRIVATE.exists() and not (OUT/'qualification.json').exists();protect_directory(PRIVATE)
kit=ROOT/'.local/releases/r1-0.1.23';before=verify(kit)
output=ROOT/'.local/releases/disposable-refused-stale-application-inputs'
assert not output.exists()
reference=ROOT/'.local/release-kit-rehearsal/private/reference/operator'
repro=ROOT/'docs/evidence/G7/20261104-core23-repro-01/qualification.json'
build=ROOT/'docs/evidence/G7/20261104-core23-uninstall-image-03/candidate-build.json'
assert repro.is_file() and build.is_file()
python=ROOT/'.local/release-kit-rehearsal/operator/Scripts/python.exe'
shared=['--application-reproduction',str(repro),'--application-build',str(build)]
commands=[('assembly',ROOT/'release/assemble.py',['--output',str(output),'--catalog',str(reference.parent.parent/'catalog'),
           '--trust',str(reference/'trust.json'),'--receipt',str(PRIVATE/'assembly-receipt.json'),*shared]),
          ('refresh',ROOT/'release/refresh_draft.py',[str(kit),'--receipt',str(PRIVATE/'refresh-receipt.json'),*shared])]
rows=[];streams=[]
for label,script,args in commands:
    result=subprocess.run([str(python),'-I',str(script),*args],capture_output=True,timeout=60)
    for ext,data in [('stdout',result.stdout),('stderr',result.stderr)]:
        path=PRIVATE/(label+'.'+ext)
        with path.open('xb') as f:f.write(data)
        streams.append(path)
    assert result.returncode!=0 and b'Checkout/build source input set differs' in result.stderr,label
    assert not output.exists() and not (PRIVATE/(label+'-receipt.json')).exists()
    rows.append(dict(command=label,exit_code=result.returncode,reason='checkout_build_source_input_set_differs',
                     output_or_receipt_created=False,stream_sha256=hashlib.sha256(result.stdout+result.stderr).hexdigest()))
assert before==verify(kit)
sources=[ROOT/name for name in ['release/application_inputs.py','release/assemble.py','release/refresh_draft.py',
    'tests/test_release_application_inputs.py','docs/release-kit.md','docs/architecture-decisions/0058-explicit-release-application-inputs.md']]+[Path(__file__)]
for path in sources:
    if path.suffix=='.py':ast.parse(path.read_text())
known=json.loads((reference.parent/'qualification-known-values-worker.json').read_bytes())
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),{k:base64.b64decode(v) for k,v in known.items()})
assert not [f for path in sources+streams for f in scanner.inspect_file(path,str(path.relative_to(ROOT)))]
receipt=dict(result='passed_actual_stale_receipt_refusals_and_source_binding_tests',utc=datetime.now(timezone.utc).isoformat(),
    source_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
    actual_commands=rows,existing_kit_components_verified_unchanged=len(before['files']),
    unit_test=dict(command='python -I -m unittest discover -s tests -p test_release_application_inputs.py -v',
                   tests=9,result='passed_before_this_CLI_check',scope='temporary inputs plus real tiny-kit refresh identity guards'),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    privacy=dict(known_values=len(known),findings=0),
    limits=['Both actual CLIs refused before output/receipt creation, Git archive, image inspection/export or deployment; no Docker asset or application data changed.',
            'Existing draft is preserved at its historical source/image identity, not promoted to final release.',
            'Actual final qualified candidate/build/reproduction is still required; valid fixture tests are not final kit assembly, BOOT02 or OPS03.',
            'Receipt selection is operator-reviewed evidence, not publisher authentication or independent execution approval.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(dict(result=receipt['result'],actual_refusals=len(rows),unit_tests=9,kit_files_unchanged=len(before['files']),privacy_findings=0)))
