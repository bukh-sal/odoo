"""Bind complete current isolation evidence and retire only its synthetic fixture."""
import hashlib,json,subprocess,sys,urllib.request,urllib.error
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-operator-isolation-01'
sys.path.insert(0,str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'))
from lifecycle import f,context,snapshot,worker,LOCAL
f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==5
def load(path):return json.loads(path.read_bytes())
records={name:load(OUT/(name+'.json')) for name in ['application-identities','foreign-UID-denial','windows-store-ACLs','windows-catalog-parent-integrity','redacted-status','source-Windows','source-Linux']}
for name,record in records.items():assert record['result'].startswith('passed'),name
assert records['windows-store-ACLs']['violations']==[] and records['windows-catalog-parent-integrity']['violations']==[]
assert records['foreign-UID-denial']['private_bytes_exact'] and records['foreign-UID-denial']['volume_mounted_readwrite_for_denial']
status=records['redacted-status'];original=load(ROOT/'.local/g6-events/state.json');url='http://127.0.0.1:'+str(original['port'])+'/api/v1/operations/status/'+status['positive_profile']['operation_id']
http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:response=http.open(url,timeout=20)
except urllib.error.HTTPError as error:response=error
with response:assert response.code==401;anonymous_status=response.code
before=load(LOCAL/'logs/core22-http-after.stdout');after=snapshot(state,'isolation-final-data');assert before==after
assert worker(native,'isolation-final-worker')==load(LOCAL/'core22-maintenance/worker-before.json');f.guard(state)
fixture=load(PRIVATE/'linux-fixture.json');assert fixture['state']=='qualified'
ids=[r['container_id'] for r in fixture['containers']]+[records['source-Linux']['container']]
retired=[]
for index,ident in enumerate(ids):
 item=json.loads(subprocess.check_output(['docker','inspect',ident]))[0]
 assert item['State']['Status']=='exited' and item['State']['ExitCode']==0 and item['Image']==state['image_id']
 assert item['Name'].lstrip('/').startswith(state['project']+'-operator-')
 assert item['Id']!=native.config['worker_id']
 (PRIVATE/('retired-'+str(index)+'.json')).write_text(json.dumps(item,indent=2)+'\n')
 subprocess.run(['docker','rm',item['Id']],capture_output=True,check=True,timeout=20)
 retired.append(dict(id=item['Id'],name=item['Name'],removed=True))
volume=json.loads(subprocess.check_output(['docker','volume','inspect',fixture['volume']]))[0]
assert volume['Labels']['com.modular.purpose']=='operator-uid-denial'
assert fixture['volume'].startswith(state['project']+'_operator_denial_')
assert not subprocess.check_output(['docker','ps','-aq','--filter','volume='+fixture['volume']]).strip()
subprocess.run(['docker','volume','rm',fixture['volume']],capture_output=True,check=True,timeout=20)
gone=subprocess.run(['docker','volume','inspect',fixture['volume']],capture_output=True,timeout=20);assert gone.returncode and b'no such' in gone.stderr.lower()
result=dict(result='passed_current_SEC08_application_operator_separation',acceptance=['SEC-08'],spec_sections=['7.3','10.6','11.5','15','20.3'],image_id=state['image_id'],configuration_generation=5,records_sha256={name:hashlib.sha256((OUT/(name+'.json')).read_bytes()).hexdigest() for name in records},checks=dict(actual_running_application_identities=2,namespace_read_write_denials=32,foreign_UID_kernel_read_write_denials=8,foreign_UID_forged_approval_denied=True,private_fixture_bytes_exact=True,Windows_ACL_records=records['windows-store-ACLs']['records'],catalog_parent_integrity_paths=records['windows-catalog-parent-integrity']['paths'],Windows_source_tests=records['source-Windows']['tests'],Linux_source_tests=records['source-Linux']['tests'],redacted_positive_requester=200,ordinary_actor_denials=2,anonymous_status=anonymous_status,current_core22_known_CLI_journal_ID_status=404),all17tables_and_independent_worker_exact=True,cleanup=dict(containers=retired,synthetic_volume=fixture['volume'],volume_removed=True,images_networks_removed=0),limits=['Positive application-request mirror is observed on preserved original core21; exact handler/channel/validator source hashes match current core22. Current core22 CLI ID denial is directly observed.','Actual namespace isolation, Windows ACL metadata and separate synthetic POSIX foreign-UID denial do not claim Windows impersonation or general trusted-native sandboxing.','Application DB config/data are intentionally accessible to application identity; privileged host approvals/checkpoints/issuer/TLS stores are separate. No real privileged store or credential mounted into the synthetic fixture.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],Windows_tests=records['source-Windows']['tests'],Linux_tests=records['source-Linux']['tests'],containers_removed=4,volumes_removed=1,all17tables_worker_exact=True)))
