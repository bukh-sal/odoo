"""Trusted bootstrap for a new native-app test site, deliberately without workspaces."""
import json
from pathlib import Path

settings = json.loads(Path('/run/mp-bootstrap/reference.json').read_bytes())
assert env.cr.dbname == settings['database']
assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
assert not env['mp.principal'].search_count([])
assert not env['mp.workspace'].search_count([])
assert not env['mp.plugin.installation'].search_count([])
for key, value in [('mp.site_id', settings['site_id']),
                   ('mp.deployment_id', settings['deployment_id']), ('mp.release_generation', '1')]:
    env['ir.config_parameter'].set_param(key, value)
env.ref('base.user_admin').with_context(no_reset_password=True).write({'password': settings['passwords']['admin']})
users = {}
for key in ['operator', 'alice', 'bob', 'worker']:
    user = env['res.users'].with_context(no_reset_password=True).create(dict(
        name='Tasks test '+key.title(), login='at_'+key, password=settings['passwords'][key],
        group_ids=[(6, 0, env.ref('base.group_user').ids)]))
    principal = env['mp.principal'].create(dict(name=user.name, user_id=user.id, kind='human'))
    users[key] = dict(id=user.id, login=user.login, principal_id=principal.public_id)
    if key == 'operator':
        env['mp.application.operator'].create(dict(principal_id=principal.id))
env.cr.commit()
print('MP_REFERENCE_RESULT='+json.dumps(dict(site_id=settings['site_id'], users=users,
                                          workspaces={}, installed_plugins=[]), sort_keys=True))
