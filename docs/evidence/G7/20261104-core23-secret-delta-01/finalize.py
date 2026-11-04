"""Verify the incremental proof before retiring the exact owned export file."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core23-secret-delta-01'
record=json.loads((OUT/'image-delta.json').read_bytes())
assert record['findings']==[] and record['newly_generated_value_hits']==0
assert record['regular_members']==23913 and record['new_byte_sequences_scanned']==20
raw=(PRIVATE/'inventory.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==record['inventory_sha256']
assert len(json.loads(raw))==23913
archive=PRIVATE/'application-image.tar'
assert archive.resolve().parent==PRIVATE.resolve() and not archive.is_symlink()
assert archive.stat().st_size==record['export_bytes']
with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
qualified=dict(result='passed_current_app_layer_secret_delta',utc=datetime.now(timezone.utc).isoformat(),
 image=record['image'],base_image=record['base_image'],known_values=123,prior_qualified_identical_members=record['reused_identical_member_scans'],
 current_regular_members=23913,new_byte_sequences_scanned=20,new_secret_value_hits=0,unreviewed_findings=0,
 prior_scope='../20261104-image-secret-audit-01/qualification.json',delta='image-delta.json',
 archive_sha256=digest,archive_bytes=archive.stat().st_size,
 limits=['Current immutable app layer/config/history delta only; prior final exact-image proof retained for unchanged worker/PostgreSQL/selected proxy.',
 'This does not independently close Git history/current served assets/diagnostics, bundled vulnerability review, reproducibility or complete OPS03/G7.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(qualified,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
assert json.loads((OUT/'qualification.json').read_bytes())==qualified
archive.unlink()
assert not archive.exists()
with (OUT/'retention.json').open('x',encoding='utf8') as f:json.dump(dict(result='retired_exact_owned_image_export_after_verified_fsynced_proof',archive_sha256=digest,bytes_released=qualified['archive_bytes'],images_removed=0,containers_created=0,volumes_created=0,unknown_assets_touched=0,private_inventory_and_finding_cache_retained=True),f,indent=2);f.write('\n')
print(json.dumps(dict(result=qualified['result'],export_retired=True,bytes_released=qualified['archive_bytes'])))
