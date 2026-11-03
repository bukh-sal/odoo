"""Remove only redundant verified blob copies and terminal read-only observers."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
def load(path):return json.loads(path.read_bytes())
assert load(OUT/'repository-triage.json')['unreviewed_findings']==0
inventory=load(PRIVATE/'history-inventory.json');findings=load(OUT/'implementation-history.json')['findings']
keep={r['git_blob'] for r in findings};cache=(PRIVATE/'history-blobs').resolve();removed=0;bytes_removed=0
assert cache.is_relative_to((ROOT/'.local/g7-image-secret-audit-01').resolve())
assert {p.name for p in cache.iterdir()}==keep
removed=sum(r['oid'] not in keep for r in inventory)
bytes_removed=sum(r['size'] for r in inventory if r['oid'] not in keep)
targets=[load(ROOT/'.local/g7-fresh-release-01/target21/operator/target.json'),load(ROOT/'.local/g6-events/operator/target.json')]
ids=subprocess.check_output(['docker','ps','-aq','--filter','status=exited']).decode().split()
info=json.loads(subprocess.check_output(['docker','inspect',*ids]));retired=[];archive=PRIVATE/'terminal-observer-diagnostics';archive.mkdir(exist_ok=True)
for item in info:
 name=item['Name'].lstrip('/');target=next((t for t in targets if name.startswith(t['project']+'-op-') and name.endswith('-dispatch-observe')),None)
 if target is None:continue
 labels=item['Config']['Labels'];assert item['State']['Status']=='exited' and item['State']['ExitCode']==0
 assert labels['com.modular.deployment']==target['deployment_id'] and labels['com.modular.operation'] in name and item['Id']!=target['worker_id']
 (archive/(item['Id']+'.json')).write_text(json.dumps(item,indent=2)+'\n')
 r=subprocess.run(['docker','logs',item['Id']],capture_output=True,timeout=20)
 assert r.returncode==0 or (item['HostConfig']['LogConfig']['Type']=='none' and b'configured logging driver does not support reading' in r.stderr)
 (archive/(item['Id']+'.stdout')).write_bytes(r.stdout);(archive/(item['Id']+'.stderr')).write_bytes(r.stderr)
 subprocess.run(['docker','rm',item['Id']],capture_output=True,check=True,timeout=20)
 gone=subprocess.run(['docker','inspect','--type','container',item['Id']],capture_output=True,timeout=20);assert gone.returncode and b'no such' in gone.stderr.lower()
 retired.append(dict(id=item['Id'],name=name,exit_code=0,removed=True))
report=dict(result='removed_verified_redundant_audit_blobs_and_terminal_observers',history_blob_copies_removed=removed,bytes_removed=bytes_removed,exact_finding_blob_copies_retained=len(keep),retired_observers=retired,containers_removed=len(retired),images_volumes_networks_removed=0,active_image_scan_export_untouched=True,current_and_checkpoint_roles_retained=True,limits=['Only exited0 read-only dispatch-observe helpers with exact project/deployment/operation labels; current apps/workers and unrelated Docker assets untouched.','All Git objects remain in Git; private inventory and exact finding blobs retained for audit.'])
with (OUT/'completed-cleanup.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],history_copies_removed=removed,bytes_removed=bytes_removed,containers_removed=len(retired))))
