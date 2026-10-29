"""Existing requester can read only redacted journal status; IDs grant no access."""
from datetime import datetime,timezone
import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle';sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from modular_platform.contracts import validate_operations_view
from lifecycle_data_probe import sql

def main():
 dest=OUTPUT/'redacted-status.json';assert not dest.exists();target=json.loads((LOCAL/'operator/target.json').read_text());fixture=json.loads((LOCAL/'fixtures.json').read_text());reader=DockerObserver(target)
 statement="BEGIN READ ONLY; SELECT jsonb_build_object('operation_id',o.public_id,'actor_id',u.id,'login',u.login,'requester',p.public_id,'mirror',o.journal_mirror) FROM mp_operation_request o JOIN mp_principal p ON p.id=o.requested_by JOIN res_users u ON u.id=p.user_id JOIN mp_application_operator a ON a.principal_id=p.id WHERE o.site_public_id=(SELECT value FROM ir_config_parameter WHERE key='mp.site_id') AND o.journal_mirror IS NOT NULL AND a.state='active' AND p.state='active' AND u.active ORDER BY o.id DESC LIMIT 1; ROLLBACK;"
 row=json.loads(sql(reader,statement));validate_operations_view(row['mirror']);assert row['actor_id']==fixture['users']['operator']['id']
 spec=importlib.util.spec_from_file_location('current_http_probe',ROOT/'docs/evidence/G5/20261029-http-security-02/probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 def client():
  c=m.Client('development');c.base='http://127.0.0.1:18080';c.authority='g5.localhost:18080';c.origin='http://g5.localhost:18080';return c
 def login(c,actor):
  code,value,_,_=c.request('/web/session/authenticate',dict(jsonrpc='2.0',id=1,method='call',params=dict(db=target['sites'][0]['database'],login=fixture['users'][actor]['login'],password=(LOCAL/'bootstrap-password').read_text().strip())),headers={'Origin':c.origin});assert code==200 and value['result']['uid']==fixture['users'][actor]['id'];code,value,_,_=c.request('/api/v1/client-release');assert code==200;c.release=value['data']['token']
 operator=client();login(operator,'operator');path='/api/v1/operations/status/'+row['operation_id'];code,value,_,raw=operator.request(path,headers={'X-MP-Client-Release':operator.release});assert code==200;view=value['data'];validate_operations_view(view);assert view['source']=='operator_journal_mirror' and view['requested_by']==row['requester'] and view['stale'] is True
 forbidden={'approval','acknowledgments','operator_id','authorized_operators','owner_identity','details','credentials','password','db_password','admin_passwd','native_trace','control_path'}
 def inspect(v):
  if isinstance(v,dict):
   assert not (set(v)&forbidden)
   for x in v.values():inspect(x)
  elif isinstance(v,list):
   for x in v:inspect(x)
 inspect(view);assert view['control_authority']=='independent_local_os';denials=[]
 for actor in ['alice','bob']:
  c=client();login(c,actor);code,value,_,_=c.request(path,headers={'X-MP-Client-Release':c.release});assert code==403 and value['error']['code']=='FORBIDDEN';denials.append(dict(actor=actor,status=code,error=value['error']['code']))
 c=client();code,value,_,_=c.request(path,headers={'X-MP-Client-Release':operator.release});assert code==401;denials.append(dict(actor='anonymous',status=code))
 report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),existing_operation_id=row['operation_id'],target='lifecycle18',source='operator_journal_mirror',authorized_requester_status=200,stale_historical_mirror_explicit=True,redacted_top_level_fields=sorted(view),history_has_no_private_details=True,denials=denials,privileged_status_or_approval_store_written=False,limits=['Read-only existing operation status; no new request, mirror refresh, approval, native action or application role change.','A historical mirror honestly reports stale=true and conveys no execution authority. Necessary application DB configuration is distinct from privileged host stores.'])
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',authorized_status=True,private_fields_absent=True,unauthorized_denials=len(denials))))
if __name__=='__main__':main()
