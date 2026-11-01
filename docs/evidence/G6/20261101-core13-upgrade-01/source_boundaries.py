"""Reuse only exact native queue/job/identity source boundaries from core12."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
old=json.loads((ROOT/'docs/evidence/G6/20261101-core12-candidate-01/candidate-build.json').read_text())
new=json.loads((ROOT/'docs/evidence/G6/20261101-core13-candidate-01/candidate-build.json').read_text())
paths=['platform_addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/job_runner.py',
    'packages/platform_sdk/modular_platform/durable.py','platform_addons/mp_example_notes/jobs.py']
paths.extend(p for p in old['source_sha256'] if p.startswith('platform_addons/mp_identity/'))
for path in paths:
    assert old['source_sha256'][path]==new['source_sha256'][path]==hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
changed='platform_addons/mp_core/external_job.py'
assert old['source_sha256'][changed]!=new['source_sha256'][changed]
result=dict(result='passed_exact_native_source_boundaries',previous_image=old['image_id'],current_image=new['image_id'],
    exact_files=paths,current_source_sha256={p:new['source_sha256'][p] for p in paths},
    new_external_bridge_qualified_by='20261101-external-finalize-01 candidate source; installed remote path still pending',
    retained_native_evidence=['../20261101-core12-runner-01/qualification.json','../20261101-identity12-upgrade-01/qualification.json'],
    actual_new_evidence=['preservation.json','completed.json'],limits=['No new lease/death/revocation experiment or complete SVC acceptance is claimed.',
        'Changed metadata lifecycle, native feature and external operator/bridge paths need their actual installed integration checks.'])
(OUT/'source-boundaries.json').write_text(json.dumps(result,indent=2)+'\n')
print('Native job/queue/identity sources exact; changed external bridge explicitly excluded from retained proof')
