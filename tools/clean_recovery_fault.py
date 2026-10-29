"""A new approved native fault in the clean OPS02 project, never a replay."""
import argparse,configparser,hashlib,json,secrets,subprocess,sys,urllib.request,re,shutil,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from clean_recovery_fixture import ROOT,LOCAL,OUTPUT,load,write,save,phase,guard,native,command
from clean_recovery_auth import execute_code
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError,protect_directory
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.plans import data_digest
from modular_platform.uninstall_planning import prepare_current_image_uninstall
from modular import configuration
from lifecycle_data_probe import sql,SCHEMA,BUSINESS_SQL
import r1_probe

class InjectedNativeCommitFault(OperatorError):pass

def context():
 state=load(LOCAL/'state.json');guard(state);target=LOCAL/'operator/target.json';cfg=load(target);validator=configuration(LOCAL/'operator/trust.json');catalog=Catalog(LOCAL/'operator/catalog',validator,readonly=True);reader=DockerObserver(cfg);return state,target,cfg,validator,catalog,reader

def prepare():
 state,target,cfg,validator,catalog,reader=context();assert state['phase']=='native_auth_seeded' and not (LOCAL/'fault-operation.json').exists();fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;private={};operator=None
 for actor in ['alice','operator']:
  client=r1_probe.Client(state,fixture,actor);cookie=next(c.value for c in client.jar if c.name=='session_id');private[actor]=dict(session_id=cookie,release_token=client.release_token)
  if actor=='operator':operator=client
 write(LOCAL/'session.json',private)
 req=urllib.request.Request(operator.base+'/app/org.example.notes/?workspace='+fixture['workspaces']['A']['public_id'])
 with operator.http.open(req,timeout=30) as response:html=response.read()
 paths=sorted(set(re.findall(rb'(?:src|href)=[\"\x27]([^\"\x27]*/web/assets/[^\"\x27]+)',html)));assets=[]
 for raw in paths:
  path=raw.decode()
  if not path.startswith('/'):continue
  with operator.http.open(operator.base+path,timeout=30) as response:data=response.read();assert response.status==200 and response.geturl()==operator.base+path;assets.append(dict(path=path,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),content_type=response.headers['Content-Type']))
 assert len(assets)>=2;save('assets-before-fault.json',assets)
 # Preexisting short-lived technical credentials must not survive restoration.
 token=secrets.token_urlsafe(32);assert not (LOCAL/'service-token').exists();(LOCAL/'service-token').write_text(token,encoding='utf8');doc=reader.state(reader.read(),catalog.snapshot())['state'];installation=next(i['installation_id'] for i in doc['installations'] if i['plugin_id']=='org.example.notes' and i['workspace_id']==fixture['workspaces']['A']['public_id'])
 # Use the server's validated principal, not a backing user ID as principal ID.
 prefix="p=env['mp.principal'].search([('public_id','=',"+repr(fixture['users']['worker']['principal_id'])+")]);assert len(p)==1\n"
 vals=dict(name='OPS02 short-lived proof',workspace_id=fixture['workspaces']['A']['id'],token_digest=hashlib.sha256(token.encode()).hexdigest(),installation_public_id=installation,actions='read')
 code="from datetime import timedelta\nfrom odoo import fields\n"+prefix+"assert not env['mp.service.credential'].search_count([('name','=','OPS02 short-lived proof')])\nvalues="+repr(vals)+"\nvalues.update(principal_id=p.id,expires_at=fields.Datetime.now()+timedelta(minutes=5))\nc=env['mp.service.credential'].create(values)\nenv.cr.commit()\nprint('MP_TECH_CREDENTIAL='+str(c.id))\n"
 raw=native(state,'technical-credential-fixture',[],code);rows=[l.split('MP_TECH_CREDENTIAL=',1)[1] for l in raw.decode().splitlines() if l.startswith('MP_TECH_CREDENTIAL=')];assert len(rows)==1;write(LOCAL/'technical-credential.json',dict(id=int(rows[0]),initial_state='active'))
 obs=reader.read();snapshot=catalog.snapshot();document=reader.state(obs,snapshot);impact=reader.native_impact(obs,catalog,site_id=cfg['sites'][0]['site_id'],requested=['mp_example_notes_labels']);targets=[dict(installation_id=p['installation_id'],site_id=impact['site_id'],workspace_id=w,plugin_id=p['plugin_id'],action='uninstall') for p in impact['plugins'] for w in p['workspace_ids']];assert {t['plugin_id'] for t in targets}=={'org.example.notes_labels'} and len(targets)==2
 bundle=prepare_current_image_uninstall(document,obs['sites'],snapshot,impact=impact,targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'));save('fault-bundle.json',bundle);write(LOCAL/'fault-operation.json',dict(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],configuration=cfg));phase(state,'registering_fault_operation');prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'operator/trust.json')];options=['--deployment-config',str(target),'--catalog',str(LOCAL/'operator/catalog')]
 command('register-fault',prefix+['operations','--store',str(LOCAL/'operator/control'),'register','--bundle',str(OUTPUT/'fault-bundle.json')]+options);command('approve-fault',prefix+['operations','--store',str(LOCAL/'operator/control'),'approve',bundle['plan']['operation_id'],'--plan-hash',bundle['plan_hash'],'--ack-destructive','--noninteractive']+options);write(LOCAL/'fault-operation.json',dict(state='approved',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],configuration=cfg));phase(state,'fault_approved');save('fault-authority-before.json',RestoreExecutor(NativeExecutor(OperatorStore(LOCAL/'operator/control'),target,LOCAL/'operator/catalog',validator))._authority(state['active_db'])[0]);print(json.dumps(dict(result='approved_new_destructive_fixture_operation',operation_id=bundle['plan']['operation_id'],targets=2)))

def apply():
 state,target,cfg,validator,catalog,reader=context();record=load(LOCAL/'fault-operation.json');assert state['phase']=='fault_approved' and record['state']=='approved' and cfg==record['configuration'];operation=record['operation_id'];store=OperatorStore(LOCAL/'operator/control');executor=NativeExecutor(store,target,LOCAL/'operator/catalog',validator);original_checkpoint=executor._checkpoint;original_private=executor._private_command
 def checkpoint(*args,**kwargs):
  result=original_checkpoint(*args,**kwargs);assert result==operation;save('checkpoint-native-auth-before.json',RestoreExecutor(executor)._authority(state['active_db'])[0]);change=execute_code(state,'rotate','post-checkpoint-native-auth');save('post-checkpoint-native-auth.json',change);save('checkpoint-native-auth-after.json',RestoreExecutor(executor)._authority(state['active_db'])[0]);assert load(OUTPUT/'checkpoint-native-auth-before.json')['native_auth_digest']!=load(OUTPUT/'checkpoint-native-auth-after.json')['native_auth_digest'];return result
 def private(args,path,**kwargs):
  result=original_private(args,path,**kwargs)
  if Path(path).name=='native.log':
   effects=[json.loads(l) for l in Path(path).read_text().splitlines() if l.startswith('{') and 'native_uninstall_effects' in l];assert len(effects)==1 and effects[0]['operation_id']==operation;write(LOCAL/'native-commit-fault.json',dict(state='committed_native_child_then_controlled_exception',operation_id=operation));raise InjectedNativeCommitFault('Explicit OPS02 native-commit fault before metadata/traffic')
  return result
 phase(state,'applying_native_commit_fault')
 with patch.object(executor,'_checkpoint',side_effect=checkpoint),patch.object(executor,'_private_command',side_effect=private):
  try:executor.apply(operation)
  except InjectedNativeCommitFault:pass
  else:raise AssertionError('Expected native commit fault did not occur')
 status=store.status(operation);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed'];assert load(LOCAL/'native-commit-fault.json')['state']=='committed_native_child_then_controlled_exception';observed=json.loads(sql(reader,"SELECT jsonb_build_object('labels_state',(SELECT state FROM ir_module_module WHERE name='mp_example_notes_labels'),'labels_column',EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='mp_example_note' AND column_name='x_notes_labels'),'notes',(SELECT count(*) FROM mp_example_note),'boards',(SELECT count(*) FROM mp_example_canvas_board));"));assert observed==dict(labels_state='uninstalled',labels_column=False,notes=4,boards=2)
 fixture=load(LOCAL/'fixtures.json');changed=json.loads(sql(reader,"UPDATE mp_membership m SET state='revoked' FROM mp_principal p,mp_workspace w WHERE m.principal_id=p.id AND m.workspace_id=w.id AND p.public_id='"+fixture['users']['alice']['principal_id']+"' AND w.public_id='"+fixture['workspaces']['B']['public_id']+"' AND m.state='active' RETURNING jsonb_build_object('role',m.role,'state',m.state);"));assert changed==dict(role='viewer',state='revoked');record.update(state='recovery_required_native_committed',status=status);write(LOCAL/'fault-operation.json',record);phase(state,'native_fault_requires_recovery');save('native-fault.json',dict(result='expected_native_commit_failure',operation_id=operation,status=status,native_effect=observed,later_membership_revocation=changed,protected_configurations_exact=True));save('current-authority-for-restore.json',RestoreExecutor(executor)._authority(state['active_db'])[0]);guard(state);print(json.dumps(dict(result='expected_failure_verified',operation_id=operation,state='recovery_required',native_commit=True,traffic_closed=True)))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args();globals()[args.action]()
