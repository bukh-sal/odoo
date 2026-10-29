"""Move sensitive diagnostic retention to the private audit store; no volumes."""
from datetime import datetime,timezone
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan';sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory

def main():
 dest=OUTPUT/'legacy-payload-log-remediation.json';assert not dest.exists();audit=protect_directory(LOCAL/'legacy-payload-diagnostics');assert not (audit/'intent.json').exists(),'Reconcile existing intent; do not replay cleanup'
 report=json.loads((OUTPUT/'packages-browser-logs.json').read_text());rows=[x for x in report['container_logs'] if x['name'].endswith(('-read-config','-checkpoint'))];assert len(rows)==53
 configs=[json.loads((ROOT/p).read_text()) for p in ['.local/operator/targets/g5.json','.local/g5-manager-upgrade/operator/target.json','.local/g5-lifecycle/operator/target.json','.local/g5-dispatch/operator/target.json']];byproject={c['project']:c for c in configs};records=[]
 # Verify all targets and preserve private full inspections BEFORE removing any.
 for row in rows:
  result=subprocess.run(['docker','inspect',row['id']],capture_output=True,timeout=20);assert result.returncode==0;info=json.loads(result.stdout)[0];config=byproject[row['project']];name=row['name'];match=re.fullmatch(re.escape(config['project'])+r'-op-([a-f0-9-]{36})-(read-config|checkpoint)',name);assert match and info['Name']=='/'+name and info['Id'].startswith(row['id'])
  assert info['State']['Status']=='exited' and not info['State']['Running'] and info['Config']['Labels']['com.modular.operation']==match[1] and info['Config']['Labels']['com.modular.deployment']==config['deployment_id']
  assert set(m['Name'] for m in info['Mounts'] if m['Type']=='volume')=={config['project']+'_appconfig',config['project']+'_filestore'} and all(not m['RW'] for m in info['Mounts'] if m['Type']=='volume')
  assert not info['HostConfig']['PortBindings'] and info['HostConfig']['NetworkMode']=='none' and info['HostConfig']['ReadonlyRootfs']
  private=LOCAL/'container-logs'/row['id'];raw=private.read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['bytes']
  fresh=subprocess.run(['docker','logs',info['Id']],capture_output=True,timeout=20);assert fresh.returncode==0 and fresh.stdout+b'\n'+fresh.stderr==raw
  (audit/(row['id']+'.inspect.json')).write_bytes(result.stdout)
  records.append(dict(**row,container_id=info['Id'],operation_id=match[1],kind=match[2],verified_exited=True,readonly_owned_volumes=True,private_diagnostics_preserved=True,inspect_sha256=hashlib.sha256(result.stdout).hexdigest()))
 (audit/'intent.json').write_text(json.dumps(dict(records=records,action='remove exact exited disposable helper containers without volumes; private stdout and inspections preserved'),indent=2)+'\n',encoding='utf8')
 (audit/'progress.jsonl').touch(exist_ok=False)
 for record in records:
  result=subprocess.run(['docker','rm',record['container_id']],capture_output=True,timeout=30);assert result.returncode==0
  with (audit/'progress.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps(dict(container_id=record['container_id'],removed=True,volumes_removed=False))+'\n')
  print(json.dumps(dict(state='removed_verified_exited_payload_helper',kind=record['kind'],done=sum(1 for _ in (audit/'progress.jsonl').open()))),flush=True)
 remaining=subprocess.check_output(['docker','ps','-aq','--no-trunc']).decode().split();assert all(r['container_id'] not in remaining for r in records)
 result=dict(result='passed_private_retention_and_daemon_cleanup',utc=datetime.now(timezone.utc).isoformat(),containers=len(records),config_children=sum(r['kind']=='read-config' for r in records),checkpoint_children=sum(r['kind']=='checkpoint' for r in records),records=records,limits=['Only exact exited read-only/no-network disposable maintenance helpers removed; no force, no volume/network/image/database deletion.','Original diagnostics and full inspections retained in owner-protected .local/g5-secret-scan, outside Git/build context; public original redacted findings preserved.','No credential is published. Docker operator already has private config-volume authority; no external disclosure observed, no broad protected account rotation required.','Existing application/native workers, operation journals, recovery checkpoints and DB/filestore volumes untouched.'])
 dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=result['result'],containers=len(records))))
if __name__=='__main__':main()
