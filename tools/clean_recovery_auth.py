"""Current native credential changes used only by the clean recovery rehearsal."""
import json,secrets,base64
from pathlib import Path
from clean_recovery_fixture import LOCAL,OUTPUT,load,write,save,phase,guard,native,command

CODE='''from pathlib import Path
import base64,cbor2,json,secrets
from datetime import timedelta
from odoo import fields
from cryptography.hazmat.primitives.asymmetric import ec
fixture=json.loads(FIXTURE)
assert env.cr.dbname==DATABASE
mode=MODE
probe=env['res.users'].search([('login','=','g5_recovery_auth_probe')])
def passkey(user):
 key=ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
 cose=cbor2.dumps({1:2,3:-7,-1:1,-2:key.x.to_bytes(32,'big'),-3:key.y.to_bytes(32,'big')})
 # Fixed OS-operator fixture only: native registration also creates keys through a private privileged path.
 row=env['auth.passkey.key'].with_user(user).sudo().create({'name':'Recovery native key '+mode,'credential_identifier':secrets.token_urlsafe(32),'sign_count':5 if mode=='seed' else 17})
 env.cr.execute('UPDATE auth_passkey_key SET public_key=%s WHERE id=%s',[base64.b64encode(cose).decode(),row.id])
 return row.id
if mode=='seed':
 assert not probe
 probe=env['res.users'].with_context(no_reset_password=True).create({'name':'Recovery native auth probe','login':'g5_recovery_auth_probe','password':Path('/run/mp-bootstrap/native-auth-password').read_text().strip(),'group_ids':[(6,0,[env.ref('base.group_user').id,env.ref('base.group_system').id])]})
 secret=Path('/run/mp-bootstrap/totp-old-secret').read_text().strip()
 env.cr.execute('UPDATE res_users SET totp_secret=%s,totp_last_counter=10 WHERE id=%s',[secret,probe.id])
 key_id=passkey(probe)
 probe.invalidate_recordset();assert probe.sudo().totp_enabled
 env['auth_totp.device'].with_user(probe)._generate('browser','Recovery remembered device',fields.Datetime.now()+timedelta(days=1))
else:
 assert len(probe)==1
 env['res.users'].browse(fixture['users']['alice']['id']).with_context(no_reset_password=True).write({'password':Path('/run/mp-bootstrap/alice-new-password').read_text().strip()})
 probe.with_context(no_reset_password=True).write({'password':Path('/run/mp-bootstrap/native-auth-new-password').read_text().strip(),'group_ids':[(6,0,env.ref('base.group_user').ids)]})
 secret=Path('/run/mp-bootstrap/totp-new-secret').read_text().strip()
 env.cr.execute('UPDATE res_users SET totp_secret=%s,totp_last_counter=20 WHERE id=%s',[secret,probe.id])
 env['auth.passkey.key'].search([('create_uid','=',probe.id)]).unlink();key_id=passkey(probe)
 probe.invalidate_recordset();assert probe.sudo().totp_enabled
env.cr.commit()
print('MP_NATIVE_AUTH='+json.dumps({'probe_user_id':probe.id,'current_passkey_id':key_id,'TOTP_enabled':True,'mode':mode,'material_emitted':False}))
'''

def execute_code(state,mode,label=None):
 code=CODE.replace('FIXTURE',repr((LOCAL/'fixtures.json').read_text())).replace('DATABASE',repr(state['active_db'])).replace('MODE',repr(mode))
 raw=native(state,label or 'native-auth-'+mode,[],code);rows=[l.split('MP_NATIVE_AUTH=',1)[1] for l in raw.decode().splitlines() if l.startswith('MP_NATIVE_AUTH=')];assert len(rows)==1;return json.loads(rows[0])

def seed():
 state=load(LOCAL/'state.json');guard(state);assert state['phase']=='reference_boards_ready' and not (LOCAL/'native-auth-fixture.json').exists();record=dict(phase='creating_private_seed');write(LOCAL/'native-auth-fixture.json',record)
 data={name:secrets.token_urlsafe(32) for name in ['alice-new-password','native-auth-password','native-auth-new-password']};data.update({name:base64.b32encode(secrets.token_bytes(20)).decode() for name in ['totp-old-secret','totp-new-secret']})
 for name,value in data.items():assert not (LOCAL/name).exists();(LOCAL/name).write_text(value+'\n',encoding='utf8')
 code="import json,pathlib,sys\nfor name,value in json.load(sys.stdin).items():\n p=pathlib.Path('/bootstrap')/name;assert not p.exists();p.write_text(value+'\\n');p.chmod(0o444)\nprint('Fixture authentication inputs transferred privately')"
 command('native-auth-bootstrap-files',['docker','run','--name',state['project']+'-native-auth-input','--log-driver','none','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+state['project']+'_bootstrap,target=/bootstrap','--entrypoint','/venv/bin/python',state['image_id'],'-c',code],input=json.dumps(data).encode())
 result=execute_code(state,'seed');write(LOCAL/'native-auth-fixture.json',dict(phase='seeded',**result));phase(state,'native_auth_seeded');save('native-auth-before-checkpoint.json',result)

if __name__=='__main__':
 import sys
 if sys.argv[1:] in [['--resume-seed-harness'],['--resume-device-model-name']]:
  from modular_platform.deployment import DockerObserver
  from lifecycle_data_probe import sql
  state=load(LOCAL/'state.json');guard(state);assert state['phase']==('native-auth-seed-reconciled' if sys.argv[1]=='--resume-device-model-name' else 'native-auth-seed') and load(LOCAL/'native-auth-fixture.json')['phase']=='creating_private_seed'
  reader=DockerObserver(load(LOCAL/'operator/target.json'));assert json.loads(sql(reader,"SELECT jsonb_build_array((SELECT count(*) FROM res_users WHERE login='g5_recovery_auth_probe'),(SELECT count(*) FROM auth_passkey_key),(SELECT count(*) FROM auth_totp_device));"))==[0,0,0]
  if sys.argv[1]=='--resume-device-model-name':
   assert json.loads(sql(reader,"SELECT jsonb_agg(model) FROM ir_model WHERE model LIKE 'auth%device';"))==['auth_totp.device']
   save('native-auth-seed-attempt-02.json',dict(result='fixture_model_name_error',observed='Native registered model is auth_totp.device; fixture incorrectly used auth.totp.device.',committed_probe_rows=0,next='Use actual pinned native model name, retain original credential inputs and failed containers.'))
  else:
   save('native-auth-seed-attempt.json',dict(result='native_registration_ACL_refusal',diagnosis='Direct passkey create under ordinary user is correctly disallowed. Native registration uses a private privileged path. Fixed OS-only fixture uses with_user(probe).sudo after explicit disposable-target authorization; no ACL change.',committed_probe_rows=0,credentials_reused=True))
  result=execute_code(state,'seed','native-auth-seed-device-name' if sys.argv[1]=='--resume-device-model-name' else 'native-auth-seed-reconciled');write(LOCAL/'native-auth-fixture.json',dict(phase='seeded',**result));phase(state,'native_auth_seeded');save('native-auth-before-checkpoint.json',result)
 else:
  assert not sys.argv[1:];seed()
