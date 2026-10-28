"""Explicit local provisioning on a newly initialized, disposable core-only site."""
from pathlib import Path
import json

assert env.cr.dbname.startswith('mp_disposable_r0_r1_g5_')
assert not env['mp.principal'].search_count([]),'Core site already provisioned'
assert not env['mp.plugin.installation'].search_count([]),'Plugins install through the independent executor later'
env['ir.config_parameter'].set_param('mp.site_id','G5_SITE_UUID')
env['ir.config_parameter'].set_param('mp.deployment_id','G5_DEPLOYMENT_UUID')
env['ir.config_parameter'].set_param('mp.release_generation','1')
password=Path('/run/mp-bootstrap/password').read_text().strip()
env.ref('base.user_admin').with_context(no_reset_password=True).write({'password':password})
users={};principals={}
for key,kind in [('operator','human'),('alice','human'),('bob','human'),('worker','service')]:
    user=env['res.users'].with_context(no_reset_password=True).create({'name':key.title(),'login':'g5_'+key,
        'password':password,'group_ids':[(6,0,env.ref('base.group_user').ids)]})
    users[key]=user;principals[key]=env['mp.principal'].create({'name':user.name,'user_id':user.id,'kind':kind})
workspaces={key:env['mp.workspace'].create({'name':'Personal' if key=='A' else 'Research'}) for key in ['A','B']}
for who,where,role in [('operator','A','administrator'),('operator','B','administrator'),('alice','A','administrator'),
                       ('alice','B','viewer'),('bob','B','editor'),('worker','A','viewer')]:
    env['mp.membership'].create({'principal_id':principals[who].id,'workspace_id':workspaces[where].id,'role':role})
env['mp.application.operator'].create({'principal_id':principals['operator'].id})
env.cr.commit()
print('MP_G5_RESULT='+json.dumps({'site_id':'G5_SITE_UUID','users':{key:{'id':row.id,'login':row.login,'principal_id':principals[key].public_id} for key,row in users.items()},
    'workspaces':{key:{'id':row.id,'public_id':row.public_id} for key,row in workspaces.items()},'installed_plugins':[]},sort_keys=True))
