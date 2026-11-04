"""Exercise the documented packaging path in isolated example sources, no Docker."""
import base64, hashlib, io, json, re, shutil, subprocess, sys, zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path.cwd(); OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from modular_platform.operator_os import protect_directory
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from secret_scan import Scanner

PRIVATE=ROOT/'.local/g7-developer-packaging-01'
assert not PRIVATE.exists() and not (OUT/'qualification.json').exists()
protect_directory(PRIVATE); source=PRIVATE/'source';source.mkdir();artifacts=PRIVATE/'artifacts';artifacts.mkdir()
for relative in ['packages/platform_sdk','packages/contracts','plugins/notes_labels','plugins/canvas',
                 'platform_addons/mp_example_notes_labels','platform_addons/mp_example_canvas']:
    shutil.copytree(ROOT/relative,source/relative,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ['LICENSE','COPYRIGHT']:shutil.copyfile(ROOT/name,source/name)
python=ROOT/'.local/release-kit-rehearsal/operator/Scripts/python.exe'
rows=[];streams=[]
def run(label,example,output,ok=True):
    result=subprocess.run([str(python),'-I',str(ROOT/'tools/package_reference.py'),'--source',str(source),
                          '--example',example,'--output',str(output)],capture_output=True,timeout=30)
    for ext,data in [('stdout',result.stdout),('stderr',result.stderr)]:
        path=PRIVATE/(label+'.'+ext)
        with path.open('xb') as f:f.write(data)
        streams.append(path)
    assert (result.returncode==0)==ok,label+' unexpected result; inspect private diagnostics'
    return result
def edit(path,before,after):
    text=path.read_text();assert before in text;path.write_text(text.replace(before,after),encoding='utf8')
for example,addon,old,new,visible_file,old_text,new_text in [
    ('notes_labels','mp_example_notes_labels','0.2.4','0.2.5','plugins/notes_labels/plugin.toml','Edit labels','Edit labels (developer example)'),
    ('canvas','mp_example_canvas','0.1.4','0.1.5','platform_addons/mp_example_canvas/static/src/page.js','Collect ideas. Move them forward.','Developer reference page')]:
    manifest=source/'plugins'/example/'plugin.toml';native=source/'platform_addons'/addon/'__manifest__.py'
    edit(manifest,'"version" = "'+old+'"','"version" = "'+new+'"')
    edit(source/visible_file,old_text,new_text)
    rejected=artifacts/(example+'-mismatch.mplug')
    run(example+'-version-mismatch',example,rejected,ok=False);assert not rejected.exists()
    edit(native,'19.0.'+old,'19.0.'+new)
    output=artifacts/(example+'-'+new+'.mplug');result=run(example+'-build',example,output)
    report=json.loads(result.stdout);raw=output.read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest()
    assert report['digest']==digest and report['version']==new
    # Independent local validation configuration admits only this exact synthetic
    # artifact. This is not the live operator/catalog policy or execution approval.
    validator=ArtifactValidator(TrustPolicy('curated',frozenset({digest}),False,1))
    validator.verify(output,expected_digest=digest)
    second=artifacts/(example+'-'+new+'-second.mplug');run(example+'-reproduce',example,second)
    assert second.read_bytes()==raw
    run(example+'-overwrite-refused',example,output,ok=False);assert output.read_bytes()==raw
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        root=report['plugin_id']+'/'
        target=(root+'frontend/dist/canvas.js' if example=='canvas' else root+'plugin.toml')
        assert new_text.encode() in archive.read(target)
        assert (root+'backend/odoo_addons/'+addon+'/__manifest__.py') in archive.namelist()
    rows.append(dict(example=example,version=new,digest=digest,bytes=len(raw),
        curated_validator_passed=True,reproduced_byte_exact=True,mismatched_versions_no_output=True,
        overwrite_refused_bytes_preserved=True,modified_presentation_in_archive=True))
known=json.loads((ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').read_bytes())
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),{k:base64.b64decode(v) for k,v in known.items()})
public=[ROOT/'tools/package_reference.py',ROOT/'docs/developer-guide.md',Path(__file__)]
assert not [f for p in streams+public for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))]
guide=ROOT/'docs/developer-guide.md';links=re.findall(r'\]\(([^)]+)\)',guide.read_text())
for link in links:assert (guide.parent/link.split('#')[0]).is_file(),link
receipt=dict(result='passed_documented_reference_packaging_only',utc=datetime.now(timezone.utc).isoformat(),
    examples=rows,cli_processes=len(streams)//2,operator_environment='existing_isolated_kit_Python',
    known_values=len(known),privacy_findings=0,document_links_verified=len(links),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in public},
    limits=['Isolated copies only; no tracked native plugin/version changes, import of native addon code or live catalog/trust changes.',
            'No Docker command, browser, database write, deployment, approval or worker restart was executed.',
            'Two synthetic example artifacts were independently validated and byte-reproduced; this is not final application image reproduction/BOOT02.',
            'Full final-kit fresh developer installation/extension/custom-page/permission/recovery and separate worker proof remains required.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(dict(result=receipt['result'],examples=len(rows),cli_processes=receipt['cli_processes'],privacy_findings=0)))
