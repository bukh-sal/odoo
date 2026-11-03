"""Existing requester status is redacted; knowing a CLI journal ID grants no read."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from modular_platform.deployment import DockerObserver
from modular_platform.contracts import validate_operations_view
from lifecycle_data_probe import sql
import r1_probe
def load(path):return json.loads(path.read_bytes())
original=ROOT/'.local/g6-events';target=load(original/'operator/target.json');state=load(original/'state.json');fixture=load(original/'fixtures.json')
statement="BEGIN READ ONLY; SELECT jsonb_build_object('operation_id',o.public_id,'actor_id',u.id,'requester',p.public_id,'mirror',o.journal_mirror) FROM mp_operation_request o JOIN mp_principal p ON p.id=o.requested_by JOIN res_users u ON u.id=p.user_id JOIN mp_application_operator a ON a.principal_id=p.id WHERE o.site_public_id=(SELECT value FROM ir_config_parameter WHERE key='mp.site_id') AND o.journal_mirror IS NOT NULL AND a.state='active' AND p.state='active' AND u.active ORDER BY o.id DESC LIMIT 1; ROLLBACK;"
row=json.loads(sql(DockerObserver(target),statement));assert row and row['actor_id']==fixture['users']['operator']['id'];validate_operations_view(row['mirror'])
r1_probe.r1.r0.LOCAL=original;operator=r1_probe.Client(state,fixture,'operator');path='/api/v1/operations/status/'+row['operation_id']
code,value=operator.request(path);assert code==200;view=value['data'];validate_operations_view(view)
assert view['source']=='operator_journal_mirror' and view['requested_by']==row['requester'] and view['control_authority']=='independent_local_os'
forbidden={'approval','acknowledgments','operator_id','authorized_operators','owner_identity','details','credentials','password','db_password','admin_passwd','native_trace','control_path'}
def check(value):
 if isinstance(value,dict):
  assert not (set(value)&forbidden)
  for child in value.values():check(child)
 elif isinstance(value,list):
  for child in value:check(child)
check(view);denials=[]
for actor in ['alice','bob']:
 client=r1_probe.Client(state,fixture,actor);code,value=client.request(path)
 assert code==403 and value['error']['code']=='FORBIDDEN';denials.append(dict(actor=actor,status=code))
fresh=ROOT/'.local/g7-fresh-release-01/target21';freshstate=load(fresh/'state.json');freshfixture=load(fresh/'fixtures.json');r1_probe.r1.r0.LOCAL=fresh
freshoperator=r1_probe.Client(freshstate,freshfixture,'operator')
cli=load(ROOT/'docs/evidence/G7/20261104-core22-maintenance-01/completed.json')['operation_id']
code,value=freshoperator.request('/api/v1/operations/status/'+cli);assert code==404 and value['error']['code']=='NOT_FOUND';assert value['error'].get('details') in ({},[],None)
old=load(ROOT/'.local/g7-release-runtime-audit-01/runtime-observation.json')['inventory']['files'];new=load(ROOT/'.local/g7-core22-provenance-01/runtime-observation.json')['inventory']['files']
source_paths=['addons/mp_core/operations.py','packages/platform_sdk/modular_platform/app_channel.py','packages/platform_sdk/modular_platform/contracts.py']
assert all(old[p]==new[p] for p in source_paths)
result=dict(result='passed_redacted_existing_status_and_current_core22_CLI_ID_denial',positive_profile=dict(image_id=target['image_id'],configuration_generation=target['generation'],operation_id=row['operation_id'],requester_status=200,source='operator_journal_mirror',stale=view['stale'],fields=sorted(view)),denials=denials,current_core22_CLI_journal_ID=dict(operation_id=cli,status=404,error='NOT_FOUND',no_application_request_mirror=True),exact_current_handler_and_channel_hashes={p:new[p] for p in source_paths},privileged_state_written=False,limits=['Positive existing application request is on preserved original core21; handler/channel/validator source bytes match current core22 exactly. Current core22 actual known CLI journal ID remains inaccessible via application status.','Read-only status/denials only; no new application request, mirror refresh, approval, role or execution change. Necessary application DB configuration is distinct from privileged stores.'])
with (OUT/'redacted-status.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],redacted_requester_status=200,ordinary_actor_denials=2,current_CLI_ID_status=404)))

