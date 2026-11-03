"""Verify the single static native Owl binding match against pinned source."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
report=json.loads((OUT/'packages-assets-current-logs.json').read_bytes())
assert report['known_secret_findings']==0 and len(report['findings'])==1
finding=report['findings'][0]
assert finding['rule']=='credential-literal' and finding['offset']==3061693 and finding['fingerprint']=='e728bcaadaf4f9c9fcac64dc'
assets=report['served_assets'];index=next(i for i,r in enumerate(assets) if 'served-static'+r['path']==finding['location'])
data=(PRIVATE/'served-assets'/str(index)).read_bytes();assert hashlib.sha256(data).hexdigest()==assets[index]['sha256']
source='addons/auth_password_policy/static/src/password_field.xml'
pinned=subprocess.check_output(['git','show','5c7defb49e020fec8b6bb82403a2f54eb79e92e1:'+source])
assert pinned==(ROOT/source).read_bytes()
expression=b'password='+b'"state.value"';assert expression in pinned and data[finding['offset']:].startswith(expression)
result=dict(result='passed_current_curated_archives_static_assets_and_current_logs',packages=19,decompressed_entries=report['expanded_entries'],served_assets=len(assets),current_container_logs=len(report['current_container_logs']),known_generated_findings=0,reviewed_findings=[dict(**finding,file_sha256=assets[index]['sha256'],source_path=source,source_sha256=hashlib.sha256(pinned).hexdigest(),reason='Exact pinned Owl binding to current password-field state; static template expression, no issued account credential.')],limits=report['limits'])
with (OUT/'assets-logs-triage.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],packages=19,assets=len(assets),current_logs=len(report['current_container_logs']))))
