"""Free two exact unused networks of an already archived/retired owned fixture."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
project='mp-r0-r1lifef99acae9d906'
prior=ROOT/'docs/evidence/G7/20261102-docker-retention-01/container-retirement.json'
retired=json.loads(prior.read_bytes());assert retired['by_project'][project]>0
assert project in json.loads((ROOT/'.local/g7-docker-retention/project-inventory.json').read_bytes())
assert subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).strip()==b''
targets={'3d1e68461700':project+'_edge','ec288be9e850':project+'_runtime'}
before={v for v in subprocess.check_output(['docker','network','ls','--no-trunc','--format','{{.ID}}']).decode().splitlines()}
records=[]
for prefix,name in targets.items():
 row=json.loads(subprocess.check_output(['docker','network','inspect',name]))[0]
 assert row['Id'].startswith(prefix) and row['Name']==name and not row['Containers']
 assert row['Labels']['com.docker.compose.project']==project
 assert row['Labels']['com.docker.compose.network']==name.rsplit('_',1)[1]
 records.append(row)
(PRIVATE/'retired-network-observations.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
for row in records:
 actual=json.loads(subprocess.check_output(['docker','network','inspect',row['Id']]))[0]
 assert actual['Name']==row['Name'] and actual['Labels']==row['Labels'] and not actual['Containers']
 r=subprocess.run(['docker','network','rm',row['Id']],capture_output=True,timeout=30)
 (PRIVATE/(row['Name']+'.stderr')).write_bytes(r.stderr)
 assert r.returncode==0,'Inspect exact current network state; do not retry blindly'
after=set(subprocess.check_output(['docker','network','ls','--no-trunc','--format','{{.ID}}']).decode().splitlines())
assert before-{r['Id'] for r in records}<=after
assert not ({r['Id'] for r in records}&after)
report=dict(result='retired_two_exact_unused_archived_fixture_networks',utc=datetime.now(timezone.utc).isoformat(),
 parent_work_item='G-01d2 releasekit clean-install prerequisite',project=project,
 retired=[dict(id=r['Id'],name=r['Name'],endpoints=0) for r in records],
 prior_container_retirement=dict(path=prior.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(prior.read_bytes()).hexdigest()),
 all_other_existing_network_ids_preserved=True,containers_images_volumes_removed=0,global_prune=False,
 purpose='Earlier Docker default address pool exhaustion; free exactly two unused owned subnets before one clean artifact-rehearsal realm. No active/unknown network deletion or existing user data touched.')
with (OUT/'network-retention.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],networks_removed=2,other_networks_preserved=True)))
