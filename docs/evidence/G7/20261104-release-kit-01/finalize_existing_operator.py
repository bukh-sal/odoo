"""Finalize the already-installed kit operator after its diagnosed ACL target error."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;WORK=ROOT/'.local/release-kit-rehearsal'
selected=WORK/'operator/Scripts/python.exe';source=WORK/'source';private=WORK/'private'
assert selected.is_file() and source.is_dir() and not private.exists() and not (WORK/'operator-setup.json').exists()
assert (WORK/'operator/pyvenv.cfg').read_text().find('include-system-site-packages = false')>=0
code="""import hashlib,importlib.metadata as m,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);from modular_platform.operator_os import protect_directory,verify_private_directory
private=Path(sys.argv[2]);assert not private.exists();protect_directory(private);identity=verify_private_directory(private)
print(json.dumps(dict(python=sys.version.split()[0],packages=sorted((d.metadata['Name'],d.version) for d in m.distributions()),private_verified=True,identity_sha256=hashlib.sha256(identity.encode()).hexdigest())))
"""
r=subprocess.run([str(selected),'-I','-c',code,str(source/'packages/platform_sdk'),str(private)],capture_output=True,timeout=45)
for suffix,raw in [('stdout',r.stdout),('stderr',r.stderr)]: (ROOT/'.local/g7-release-kit-01'/('operator-finalize.'+suffix)).write_bytes(raw)
assert r.returncode==0,'Inspect the actual existing child and diagnostic; do not rerun mutation'
observed=json.loads(r.stdout)
assert observed['python']=='3.12.16' and len(observed['packages'])==13
expected=json.loads((ROOT/'docs/evidence/G7/20261104-operator-python16-01/runtime-qualification.json').read_bytes())['packages']
normalize=lambda rows:sorted((name.lower().replace('_','-'),version) for name,version in rows)
assert normalize(observed['packages'])==normalize([(row['name'],row['version']) for row in expected])
manifest=json.loads((ROOT/'.local/releases/r1-0.1.23/kit-inventory.json').read_bytes())
result=dict(stage='operator_ready_application_not_initialized',source_commit=manifest['source_commit'],python=str(selected),source=str(source),private=str(private))
(WORK/'operator-setup.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
report=dict(result='passed_offline_kit_operator_install_and_existing_SDK_private_child',utc=datetime.now(timezone.utc).isoformat(),
 source_commit=manifest['source_commit'],Python=observed['python'],packages=observed['packages'],selected13_versions_exact=True,
 no_runtime_pip_in_selected_environment=True,private_directory_verified=True,OS_identity_sha256=observed['identity_sha256'],
 offline_binary_wheel_install=True,original_application_and_operator_stores_not_copied=True,
 prior_failure='Workspace root mode0700 has an OWNER RIGHTS ACE rejected by canonical SDK policy; public source workspace is not the private executor store.',
 continuation='Reused already-installed13 packages/extracted source; existing SDK created and verified a new private child. No reinstall/extraction/ACL reset of existing paths.',
 limits=['Operator setup only; no application initialization/catalog/worker/site data or Docker resources created. Separate portable application initializer and clean-install proof remain required.',
 'This is a diagnosed continuation of the original actual offline install; no claim that the corrected full setup command was independently rerun from an empty directory.'])
with (OUT/'operator-qualification.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],packages=13,private_verified=True)))
