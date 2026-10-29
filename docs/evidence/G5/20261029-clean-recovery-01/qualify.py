"""Assemble the actual completed clean rehearsal, with exact current code boundaries."""
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]; OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from clean_recovery_fixture import LOCAL, load, save, guard
from clean_recovery_data import context
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql
from modular_platform.operator_store import OperatorStore

state,target,reader,observed,fixture=context();guard(state)
assert state['phase']=='restored_resumed' and target['generation']==4
for name in ['closed-preservation.json','restored-HTTP.json','minimal-Canvas-fixture.json','recovery-kit-final.json','protected-audit.json','privacy-audit-final.json']:
    assert load(OUTPUT/name)['result']=='passed'
windows=load(OUTPUT/'source-Windows.json');linux=load(OUTPUT/'source-Linux.json')
assert windows['result']==linux['result']=='passed' and windows['tests']==41 and linux['tests']==35
for p,digest in windows['source_sha256'].items():
    assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest
    assert linux['source_sha256'][p]==digest
freeze=load(ROOT/'docs/contracts/freeze-v1.json')
assert len(freeze['files'])==87
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-after-reference-tests.json')
assert json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-before-fault.json')
operation=load(LOCAL/'fault-operation.json')['operation_id'];store=OperatorStore(LOCAL/'operator/control');status=store.status(operation)
assert status['state']=='revoked' and status['phase']=='restore_traffic_resumed' and status['traffic_resumed']
assert load(LOCAL/'canvas-reference-qualification.json')['state']=='completed_verified'
paths=list(windows['source_sha256'])+[p.relative_to(ROOT).as_posix() for p in (ROOT/'tools').glob('clean_recovery_*.py')]
result=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),acceptance=['OPS-02','MIG-06 requalification'],additional_exit_criterion='G5-X10 minimal Canvas reference-fixture setup',spec_sections=['10.5','21.4','22.3','22.5','24.4','25.5 E'],source_commit_before_change=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},image_id=target['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],operation_id=operation,generation_before=2,generation_after=4,source='Fresh PostgreSQL/template0 DB, own empty volumes/config/secrets/operator authority; actual normal packaged install of six reference scopes before checkpoint/fault.',fault='Real independently approved Labels uninstall commits; explicit fixture exception before metadata/traffic; failed DB retained.',restore='Ordinary exact-hash CLI restore into a fresh DB, closed verification, separate exact-hash reviewed resume.',preservation='Full business/schema/installations/bindings/grants/38previous file hashes, exact previous executable release apart from epoch, native private attachment and immutable asset bytes.',current_authority='Post-checkpoint native passwords/TOTP/counters/groups/passkeys and later workspace revocation retained; remembered devices/technical credentials invalidated; session secret rotated and old sessions refused.',standard_record_UI='native Odoo list/form; no frontend product changes',reference_fixture='Two explicit workspace-scoped one-card boards, repeat provisioning verifies no duplicate; one same-content save each, idempotent replay, stale revision conflict and foreign-ID denial.',windows_tests=41,linux_tests=35,contract_files=87,protected_operated_deployments_unchanged=4,protected_HTTP_fixture_unchanged=True,recovery_kit_files=load(OUTPUT/'recovery-kit-final.json')['files'],limits=['G5-X09 provenance/OPS-03 remains; G6/G7 and full R1 release unqualified.','Existing supported single-host recovery retains failed DB/current authority and independent journal. No total host/authority-loss disaster claim.','Native MFA rows/counters/groups/private digests are preserved; no hardware-authenticator ceremony or authentication subsystem rewrite.','Canvas save tests deliberately advance revisions only after exact recovery comparison. Canvas remains a minimal trusted custom-page reference.','Initial fixture SQL/cookie/line-ending/inventory/lock-name and Linux launch diagnoses retained; superseded partial evidence is not counted.','No production/public deployment, global Python modification or unknown data deletion.'])
save('qualification.json',result)
print(json.dumps(dict(result='passed',acceptance=result['acceptance'],additional='G5-X10',tests='41Windows/35Linux',freeze=87)))
