"""Static admission of one source25 candidate; no approval or deployment."""
import base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core25-accessibility-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_core_upgrade,core_python_changes
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner
assert not PRIVATE.exists();protect_directory(PRIVATE)
def load(p):return json.loads(p.read_bytes())
build=load(OUT/'candidate-build.json');base='sha256:567d2e6affdcb6a3d79789689d9d40d4c077c28e839d4f7b36f47dad3d32a1bd'
assert build['dependency_base_image']==base and build['result']=='built_not_deployed'
before=inspect_image(base);after=inspect_image(build['image_id'])
for name,value in [('base-runtime',before),('candidate-runtime',after)]:
    with (PRIVATE/(name+'.json')).open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.write('\n')
source,native=validate_core_upgrade(before,after,dict(base_image_id=base,target_image_id=build['image_id']))
expected={'addons/mp_core/__manifest__.py','addons/mp_shell/__manifest__.py','addons/mp_shell/static/src/host.css',
          'addons/mp_shell/static/src/dialog_accessibility.xml','packages/platform_sdk/modular_platform/projection.py'}
assert {row['path'] for row in source}==expected
assert native==[dict(addon='mp_core',previous_version='19.0.0.1.24',target_version='19.0.0.1.25',migrations=[]),
                dict(addon='mp_shell',previous_version='19.0.0.1.11',target_version='19.0.0.1.12',migrations=[])]
for key in ['python_metadata','python_lock_digest','python','architecture','markers']:assert before[key]==after[key]
assert len(after['python_metadata'])==77 and not core_python_changes(before,after)
assert not any(after[key] for key in ['modified_files','unexpected_addon_files','missing_addon_files'])
for key in ['artifacts','policy']:assert before['inventory'][key]==after['inventory'][key]
for name,value in build['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value,name
checks=load(OUT.parent/'20261104-core24-ui-audit-01/source25-checks.json')
for name,value in checks['source_sha256'].items():
    mapped=name.replace('platform_addons/','addons/',1) if name.startswith('platform_addons/') else name
    assert after['inventory']['files'][mapped]==value
old=load(ROOT/'.local/g7-core24-ui-audit-01/runtimes-before.json')
rows=json.loads(subprocess.check_output(['docker','inspect',*[r['id'] for r in old]],stderr=subprocess.PIPE,timeout=30))
actual=[dict(id=r['Id'],image=r['Image'],started=r['State']['StartedAt'],pid=r['State']['Pid'],mounts=r['Mounts'],networks=r['NetworkSettings']['Networks']) for r in rows]
assert old==actual and all(r['State']['Running'] for r in rows)
alias='modular-platform:dependency-base-'+OUT.name
assert subprocess.run(['docker','image','inspect',alias],capture_output=True,timeout=30).returncode!=0
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[OUT/'build.log',OUT/'candidate-build.json',Path(__file__)]
assert not [f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))]
report=dict(result='passed_static_core25_shell12_admission_not_deployed',utc=datetime.now(timezone.utc).isoformat(),
    image_id=build['image_id'],inventory_digest=after['inventory_digest'],base_image_id=base,
    source_changes=source,native_changes=native,python_distributions=77,dependency_environment_exact=True,
    packaged_artifacts_and_policy_exact=True,all_build_source_hashes_exact=True,four_running_runtimes_exact=True,
    dependency_alias_removed=True,privacy=dict(known_values=len(values),findings=0),
    evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    limits=['One immutable candidate only; current567d/config5 remains selected. No stage/review/approval/apply has occurred.',
            'Five inventoried owned correction/version source changes; unchanged host/dialog interaction behavior; actual compiled title label/close rendering still unverified.',
            'New package_reference.py tool from the source developer-path work is included by the existing Docker tools COPY and recorded build-source hashes; no new application route/execution approval.',
            'No new persistent container/volume/network; one candidate image retained for next normal independent maintenance. No UI09/BOOT02/OPS03 pass.'])
with (OUT/'candidate-admission.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],image=build['image_id'],inventory=after['inventory_digest'],source_changes=len(source),privacy_findings=0)))
