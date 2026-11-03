"""Verify already completed seven requests; no credential/HTTP replay."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import s,base,f,j,PRIVATE,op
from modular_platform.contracts import validate
state,native=s.context();assert f.load(PRIVATE/'credentials-marker.json')['state']=='sending_current_authority_cases'
responses=json.loads((j.LOCAL/'logs/worker-security-current-credentials.stdout').read_bytes())
expected=[('current',200),('old_endpoint9',403),('wrong_audience',401),('foreign_workspace',403),('payload_workspace',401),('payload_site',401),('retired_key_current_kid',401)]
assert [(x['name'],x['status']) for x in responses]==expected
for response in responses:
 if response['status']==200:
  validate('worker-response',response['body']);text='Current image approval verification';assert response['body']['data']==dict(characters=len(text),words=len(text.split()),lines=len(text.splitlines()))
 else:assert response['body']==dict(error=dict(code='UNAUTHENTICATED' if response['status']==401 else 'FORBIDDEN'))
before=json.loads((j.LOCAL/'logs/worker-security-credentials-before.stdout').read_bytes())
assert base.snapshot(state,'worker-security-credentials-finalize-after')==before
old=json.loads((j.LOCAL/'logs/worker-security-credentials-worker-before.stdout').read_bytes())[0]
current=base.worker(native,'worker-security-credentials-finalize-worker')
assert current['container_id']==old['Id'] and current['image']==old['Image'] and current['started_at']==old['State']['StartedAt'] and current['restart_count']==old['RestartCount']
assert current['mounts']==old['Mounts'] and current['networks']==old['NetworkSettings']['Networks']
operator=op(native);document=operator.publisher._document();assert document['generation']==13
assert document==f.load(s.OUT/'new-image-review.json')['plan']['document']
scope=f.load(PRIVATE/'runtime.json')['scope'];entry=next(e for e in document['endpoints'] if e['descriptor']['installation_id']==scope['installation_id'])
assert entry['descriptor']==f.load(PRIVATE/'new-endpoint.json') and entry['key_id']=='recovery19-key'
f.save('credential-status-diagnosis.json',dict(result='verified_completed_requests_without_replay',previous_harness_error='Expected403 for token/body scope mismatch; verifier correctly returns401 before configured-scope403 check',source='services/document_stats/engine.py Engine.analyze authenticates verify_worker_token first; tokens.py checks request/claim scope equality; existing test_retry_still_rejects_expired_wrong_audience_and_forged_scope asserts401',actual_seven_requests_already_completed=True,product_behavior_unchanged=True,host17tables_worker_identity_mounts_network_start_exact=True))
f.save('current-credentials.json',dict(result='passed_actual_dependency_image_current_and_stale_authority_checks',publication_generation=13,endpoint_generation=11,cases=[dict(name=x['name'],status=x['status']) for x in responses],retired_issuer_ref_refused=True,all37jobs_other17tables_and_current_worker_exact=True,private_signing_material_only_in_operator_OS=True,limits='Direct operator-signed worker verification; original actor tested by separate ordinary job. Token/body scope mismatch is401; separately signed foreign scope is403.'))
f.write(PRIVATE/'credentials-marker.json',dict(state='verified'))
print('Seven actual credential cases verified from original responses; altered payload site/workspace correctly401; no request replay',flush=True)
