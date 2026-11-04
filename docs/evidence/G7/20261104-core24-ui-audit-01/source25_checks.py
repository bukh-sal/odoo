"""Affected source checks for owned close/title correction; not installed proof."""
import ast,base64,concurrent.futures,hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core24-ui-audit-01/source25'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner
assert not PRIVATE.exists();protect_directory(PRIVATE)
commands=[('core-upgrade',[sys.executable,'-I','-m','unittest','discover','-s','tests','-p','test_core_upgrade.py','-v']),
 ('compatibility',[sys.executable,'-I','-m','unittest','discover','-s','tests','-p','test_platform_compatibility.py','-v']),
 ('deploy',[sys.executable,'-I','-m','unittest','discover','-s','tests','-p','test_platform_deploy.py','-v']),
 ('native-interactions',[r'C:\Program Files\nodejs\node.exe','tests/test_native_interactions.mjs']),
 ('freeze',[sys.executable,'-I','tools/check_contract_freeze.py'])]
def execute(item):
    name,cmd=item;result=subprocess.run(cmd,capture_output=True,timeout=90)
    for ext,raw in [('stdout',result.stdout),('stderr',result.stderr)]:
        with (PRIVATE/(name+'.'+ext)).open('xb') as f:f.write(raw)
    return dict(name=name,exit_code=result.returncode,command=cmd,stream_sha256=hashlib.sha256(result.stdout+result.stderr).hexdigest())
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(execute,commands))
assert all(row['exit_code']==0 for row in results), 'Affected check failed; inspect retained private streams'
freeze=json.loads((PRIVATE/'freeze.stdout').read_bytes());assert freeze['files']==106 and freeze['rows']==8
paths=['platform_addons/mp_shell/static/src/host.css','platform_addons/mp_shell/static/src/dialog_accessibility.xml',
       'platform_addons/mp_shell/__manifest__.py','platform_addons/mp_core/__manifest__.py','packages/platform_sdk/modular_platform/projection.py']
manifest=ast.literal_eval((ROOT/paths[2]).read_text());assert manifest['version']=='19.0.0.1.12'
assert 'mp_shell/static/src/dialog_accessibility.xml' in manifest['assets']['mp_shell.assets_host']
tree=ET.parse(ROOT/paths[1]);template=tree.find('./t');assert template.attrib['t-inherit']=='web.Dialog' and template.attrib['t-inherit-mode']=='extension'
xpath=template.find('./xpath');assert xpath.attrib==dict(expr="//div[@role='dialog']",position='attributes')
assert xpath.find('./attribute').attrib['name']=='t-att-aria-label' and xpath.find('./attribute').text=='props.title'
upstream=ET.parse(ROOT/'addons/web/static/src/core/dialog/dialog.xml');assert len(upstream.findall(".//div[@role='dialog']"))==1
unchanged=['platform_addons/mp_shell/static/src/host.js','platform_addons/mp_shell/static/src/native_interactions.js',
           'platform_addons/mp_shell/static/src/client_release.js','platform_addons/mp_shell/views/bootstrap.xml']
for name in unchanged:assert subprocess.check_output(['git','show','HEAD:'+name])==(ROOT/name).read_bytes()
known=json.loads((ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').read_bytes())
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),{k:base64.b64decode(v) for k,v in known.items()})
public=[ROOT/name for name in paths]+[Path(__file__)]
assert not [f for p in list(PRIVATE.iterdir())+public for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))]
report=dict(result='passed_core25_owned_close_and_dialog_name_source_checks_not_installed',utc=datetime.now(timezone.utc).isoformat(),
    checks=results,freeze_files=106,freeze_rows=8,unchanged_full_source=unchanged,owned_XML_extension_target_unique=True,
    source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths},
    known_values=len(known),privacy_findings=0,
    limits=['Source/tests/XML/freeze only; actual asset compilation/native template accessibility name and close glyph need immutable candidate/installed proof.',
            'No actual image build/approval/deployment or upstream file edit. Current567d/config5 stays selected; UI09 remains failed.'])
with (OUT/'source25-checks.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],affected_suites=4,freeze_files=106,privacy_findings=0)))
