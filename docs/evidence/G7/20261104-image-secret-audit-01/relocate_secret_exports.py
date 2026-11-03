"""Separate four exact protected config/backup exports from ordinary log streams."""
import hashlib,json,sys,tarfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
report=json.loads((OUT/'retained-command-logs.json').read_bytes())
expected={
 '.local/g7-fresh-release-01/target21/logs/target21-prior-mounted-config.stdout':('674a65afbe91d25e5254704e949b6adf4b595e1a284e086e11cc797c509a3f83','config'),
 '.local/g7-fresh-release-01-project-refused/logs/refused-project-volume-archive02.stdout':('a2bfcef6f0a2aea0bccafc0b6670b59433a2026958f69b932877eece9dd7e20d','backup'),
 '.local/g7-fresh-release-01-project-refused/logs/refused-project-volume-archive.stdout':('e81ce70f652132948e3d8e0582c83c657ddc6702b056e2e27a8a3d9ac9e9d2af','backup'),
 '.local/g7-production-profile-01/logs/000.stdout':('0df7cdb30da581f427e446c7f40fca5bf3201c2b0a7ec53e19be99aed17ea13c','config')}
assert {r['location'] for r in report['findings']}==set(expected) and report['known_secret_findings']==14
destination=PRIVATE/'secret-store-relocation';assert not destination.exists();protect_directory(destination)
rows=[];workspace=ROOT.resolve()
for index,(name,(digest,kind)) in enumerate(expected.items()):
 path=(ROOT/name).resolve();target=(destination/(str(index)+('.tar' if kind=='backup' else '.conf'))).resolve()
 assert path.is_relative_to(workspace) and target.is_relative_to(PRIVATE.resolve()) and not target.exists()
 raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
 if kind=='backup':assert tarfile.is_tarfile(path)
 else:assert raw.startswith(b'[options]') and b'db_password' in raw and b'admin_passwd' in raw
 path.rename(target);assert not path.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==digest
 rows.append(dict(original_path=name,private_store_path=target.relative_to(ROOT).as_posix(),sha256=digest,bytes=len(raw),type=kind,raw_bytes_preserved=True))
record=dict(result='relocated_exact_config_backup_exports_out_of_log_namespace',files=rows,original_known_findings=14,original_generic_findings=2,credential_rotation=False,rationale='Four owner-protected fixture stdout captures were explicit mounted-configuration reads and backup tar transports. They are secret stores, not ordinary application/executor logs or release deliverables. No actual current app/worker/DB/edge stream contained known credentials. Preserve exact bytes privately and exclude from release; no external exposure observed.',limits=['Original positive scan retained; this is not a retroactive clean result. Remaining log namespace must be rescanned.','No database/password/runtime/recovery-checkpoint change or broad ignore rule; only four hash-verified existing exports moved within the private workspace.'])
with (OUT/'secret-export-relocation.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],files=len(rows),raw_bytes_preserved=True)))
