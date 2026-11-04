"""Execute a second no-cache source build from the exact qualified dependency input."""
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core23-repro-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
prior=json.loads((ROOT/'docs/evidence/G7/20261104-core23-uninstall-image-03/candidate-build.json').read_bytes())
base=prior['dependency_base_image'];reference=prior['image_id']
assert reference=='sha256:14de369e46f20616e76847cbcacbcb66d5bb791808b950aaf97bc607d31d6b93'
for name,digest in prior['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
suffix=uuid4().hex[:12];tag='modular-platform:disposable-core23-repro-'+suffix;alias='modular-platform:disposable-repro-base-'+suffix
assert subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode
assert subprocess.run(['docker','image','inspect',alias],capture_output=True).returncode
command=['docker','build','--no-cache','--network=none','--build-arg','DEPENDENCY_BASE_IMAGE='+alias,
 '-f','deploy/Dockerfile.core-maintenance','--build-arg','DISTRIBUTION_POLICY='+prior['distribution_policy'],
 '--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',tag,'.']
record=dict(state='building',utc=datetime.now(timezone.utc).isoformat(),source_head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
 reference_image=reference,dependency_base=base,tag=tag,alias=alias,command=command,recorded_source_inputs_unchanged=len(prior['source_sha256']))
def save(): (PRIVATE/'state.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
save()
subprocess.run(['docker','tag',base,alias],check=True,capture_output=True,timeout=30)
assert subprocess.check_output(['docker','image','inspect',alias,'--format','{{.Id}}']).decode().strip()==base
try:
 with (OUT/'build.log').open('xb') as stream:
  result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
finally:
 assert subprocess.check_output(['docker','image','inspect',alias,'--format','{{.Id}}']).decode().strip()==base
 subprocess.run(['docker','image','rm',alias],check=True,capture_output=True,timeout=30)
assert result.returncode==0,'Inspect recorded build state/log; do not restart'
candidate=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
record.update(state='inspecting',candidate_image=candidate);save()
observed=inspect_image(candidate);expected=inspect_image(reference)
for name,data in [('candidate',observed),('reference',expected)]: (PRIVATE/(name+'-runtime.json')).write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
keys=['inventory_digest','inventory','python','architecture','markers','python_lock_digest','python_metadata','modified_files','unexpected_addon_files','missing_addon_files']
comparisons={name:observed[name]==expected[name] for name in keys}
assert all(comparisons.values()),'Real reproduction difference: retain candidate and both observations, no retry or guard relaxation'
for name,digest in prior['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
report=dict(result='passed_second_no_cache_build_declared_inventory_reproduction',utc=datetime.now(timezone.utc).isoformat(),acceptance=['BOOT-02'],
 source_head=record['source_head'],reference_image=reference,candidate_image=candidate,dependency_base=base,command=command,
 comparisons=comparisons,inventory_digest=observed['inventory_digest'],unchanged_recorded_source_inputs=record['recorded_source_inputs_unchanged'],
 actual_source_file_count=len(observed['inventory']['files']),actual_python_distributions=len(observed['python_metadata']),
 limits=['A second independent no-cache source/materialization build from the exact locked qualified dependency image, as ADR0052. RUN has network disabled. No ordinary Dockerfile cache hit is used as reproduction proof.',
 'Does not claim byte-identical image IDs/timestamps or repeat native dependency compilation under floating OS/compiler inputs. Exact dependency image is a required release artifact, with its own source/notices/qualification.',
 'No installation/deployment/runtime/database/worker changes. Fresh releasekit installation and remaining OPS03/G7 checks stay separate.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
record.update(state='qualified_pending_retention');save()
containers=subprocess.check_output(['docker','ps','-aq','--filter','ancestor='+candidate]).decode().splitlines()
assert candidate==reference or not containers
assert subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()==candidate
subprocess.run(['docker','image','rm',tag],check=True,capture_output=True,timeout=30)
record.update(state='qualified_disposable_tag_retired');save()
with (OUT/'retention.json').open('x',encoding='utf8') as f:json.dump(dict(result='retired_exact_owned_reproduction_tag_after_fsynced_proof',tag=tag,image=candidate,dependency_alias_retired=True,container_references_before=len(containers),retained_reference_image=reference,retained_dependency_base=base,volumes_networks_created=0,deployed_targets_untouched=True),f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],candidate=candidate,inventory=report['inventory_digest'],disposable_tag_retired=True)),flush=True)
