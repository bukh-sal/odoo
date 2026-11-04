"""Trusted operator provisioning in an empty disposable reference DB (Odoo shell)."""
import json
from pathlib import Path

settings=json.loads(Path('/run/mp-bootstrap/reference.json').read_bytes())
assert env.cr.dbname==settings['database'] and env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
assert not env['mp.principal'].search_count([])
assert not env['mp.plugin.installation'].search_count([])
for key,value in [('mp.site_id',settings['site_id']),('mp.deployment_id',settings['deployment_id']),('mp.release_generation','1')]:
    env['ir.config_parameter'].set_param(key,value)
env.ref('base.user_admin').with_context(no_reset_password=True).write({'password':settings['passwords']['admin']})
users={};principals={}
for key,kind in [('operator','human'),('alice','human'),('bob','human'),('worker','service')]:
    user=env['res.users'].with_context(no_reset_password=True).create(dict(name='Reference '+key.title(),login='r1_'+key,
        password=settings['passwords'][key],group_ids=[(6,0,env.ref('base.group_user').ids)]))
    users[key]=user;principals[key]=env['mp.principal'].create(dict(name=user.name,user_id=user.id,kind=kind))
workspaces={key:env['mp.workspace'].create(dict(name='Reference '+key)) for key in ['A','B']}
for who,where,role in [('operator','A','administrator'),('operator','B','administrator'),('alice','A','administrator'),
                       ('alice','B','viewer'),('bob','B','editor'),('worker','A','viewer')]:
    env['mp.membership'].create(dict(principal_id=principals[who].id,workspace_id=workspaces[where].id,role=role))
env['mp.application.operator'].create(dict(principal_id=principals['operator'].id))
env.cr.commit()
print('MP_REFERENCE_RESULT='+json.dumps(dict(site_id=settings['site_id'],users={key:dict(id=row.id,login=row.login,principal_id=principals[key].public_id) for key,row in users.items()},
    workspaces={key:dict(id=row.id,public_id=row.public_id) for key,row in workspaces.items()},installed_plugins=[]),sort_keys=True))
