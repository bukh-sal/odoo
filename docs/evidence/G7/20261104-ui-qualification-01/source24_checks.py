"""Affected host checks only; no installed UI/candidate qualification claim."""
import concurrent.futures,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));from modular_platform.operator_os import protect_directory
private=ROOT/'.local/g7-ui-qualification-01/source24-checks';assert not private.exists();protect_directory(private)
commands=[('core-upgrade',[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_core_upgrade.py','-v']),('platform-compatibility',[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_platform_compatibility.py','-v']),('platform-deploy',[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_platform_deploy.py','-v']),('native-interactions',[r'C:\Program Files\nodejs\node.exe','tests/test_native_interactions.mjs']),('syntax',[r'C:\Program Files\nodejs\node.exe','--check','platform_addons/mp_shell/static/src/host.js']),('freeze',[sys.executable,'-X','utf8','tools/check_contract_freeze.py'])]
def execute(item):
 name,cmd=item;result=subprocess.run(cmd,capture_output=True,timeout=60)
 for suffix,data in [('stdout',result.stdout),('stderr',result.stderr)]:
  with (private/(name+'.'+suffix)).open('xb') as f:f.write(data)
 return dict(name=name,command=cmd,exit_code=result.returncode,stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(execute,commands))
assert all(r['exit_code']==0 for r in results), 'Affected check failed; inspect retained private streams'
freeze=json.loads((private/'freeze.stdout').read_bytes());assert freeze['files']==106 and freeze['rows']==8
source=(ROOT/'platform_addons/mp_shell/static/src/host.js').read_text(encoding='utf8');template=source.split('static template=xml`',1)[1].split('`;',1)[0];ET.fromstring(template);ET.parse(ROOT/'platform_addons/mp_shell/views/bootstrap.xml')
old=subprocess.check_output(['git','show','037d0ec4:platform_addons/mp_shell/static/src/host.js'],stderr=subprocess.PIPE).decode()
segments=[('let workspace = null;','function error('),('    async retire(','    fail('),('    async refreshAuthority(','    async activate('),('    async activate(','    async nativeView(')]
unchanged={}
for start,end in segments:
 prior=old[old.index(start):old.index(end,old.index(start))];current=source[source.index(start):source.index(end,source.index(start))];assert prior==current,start;unchanged[start.strip()]=hashlib.sha256(current.encode()).hexdigest()
assert old[old.index('    async nativeView('):]==source[source.index('    async nativeView('):]
paths=['platform_addons/mp_shell/static/src/host.js','platform_addons/mp_shell/static/src/host.css','platform_addons/mp_shell/views/bootstrap.xml','platform_addons/mp_shell/__manifest__.py','platform_addons/mp_core/__manifest__.py','packages/platform_sdk/modular_platform/projection.py']
report=dict(result='passed_core24_shell11_affected_host_checks_not_installed_UI',utc=datetime.now(timezone.utc).isoformat(),checks=results,contract_freeze=freeze,owned_shell_and_bootstrap_XML_valid=True,native_RPC_release_retirement_authority_activation_exact_segments=unchanged,nativeView_function_exact_to_baseline=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},limits=['Core24/Shell11 source only. Current managed app remains immutable14de/core23/config4; candidate build/admission/review/upgrade/installedUI09 are not yet qualified.','Existing native behavioral seams unchanged; this does not replace actual contrast/focus/close-image/document-language/RTL/native smoke checks after normal rollout.','Public106contract files/eight rows unchanged. No packaged plugin, dependency lock or DB schema/authority change.'])
with (OUT/'source24-checks.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],checks=len(results),freeze_files=106,XML_valid=True,native_guard_segments_unchanged=len(unchanged))))
