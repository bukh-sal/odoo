"""Real native server-action actor/scope proof and native cron inventory."""
import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('core18_current',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f,j=m.f,m.j;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==25
before=m.snapshot(state,'g7-server-action-data-before')
code="""import json
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
env.cr.rollback()
def actor(workspace):return scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
env.cr.execute('SELECT count(*) FROM ir_act_server');before=env.cr.fetchone()[0]
targets={}
for w in ['A','B']:
 env.cr.execute('SELECT id FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces'][w]['id']]);targets[w]=env.cr.fetchone()[0]
try:
 action=env['ir.actions.server'].create(dict(name='ID03 rollback-only server action',model_id=env['ir.model']._get('mp.example.note').id,state='code',
   code="action={'type':'ir.actions.client','tag':'id03.probe','params':{'actor':env.uid,'sudo':env.su,'rows':records.read(['id','title'])}}"))
 def run(workspace,ident):return action.with_env(actor(workspace)).with_context(active_model='mp.example.note',active_id=ident,active_ids=[ident]).run()
 results=[]
 for grouped in [False,True]:
  if grouped:action.write({'group_ids':[(4,env.ref('base.group_user').id)]})
  value=run('A',targets['A'])['params'];assert value['actor']==FIXTURE['users']['alice']['id'] and value['sudo'] is False and [r['id'] for r in value['rows']]==[targets['A']]
  try:run('A',targets['B'])
  except AccessError:pass
  except ValueError as error:assert 'AccessError' in str(error)
  else:raise AssertionError('Foreign server action exposed data')
  results.append(dict(grouped=grouped,original_actor_no_sudo=True,own_allowed_foreign_denied=True))
 value=run('B',targets['B'])['params'];assert value['actor']==FIXTURE['users']['alice']['id'] and value['sudo'] is False and [r['id'] for r in value['rows']]==[targets['B']]
finally:env.cr.rollback();env.invalidate_all()
env.cr.execute('SELECT count(*) FROM ir_act_server');assert env.cr.fetchone()[0]==before
crons=[dict(id=c.id,model=c.model_id.model,active=c.active) for c in env['ir.cron'].search([])]
assert not any(getattr(env[c['model']],'_mp_scoped',False) for c in crons)
print('MP_SERVER_ACTION='+json.dumps(dict(result='passed',cases=results,explicit_group_viewer_read_allowed_only_own_scope=True,all_action_fixture_changes_rolled_back=True,native_crons=crons,workspace_scoped_native_crons=0)))
""".replace('FIXTURE',repr(f.load(j.LOCAL/'fixtures.json')))
raw=f.native(state,'g7-server-action-01',[],code)
rows=[json.loads(line.split('MP_SERVER_ACTION=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_SERVER_ACTION=')];assert len(rows)==1
assert m.snapshot(state,'g7-server-action-data-after')==before
f.save('server-actions.json',dict(**rows[0],native_generation=25,image=state['image_id'],all36jobs_other16tables_exact=True,
    limits='Trusted cooperating server-action code executed by real native runner; native plugins remain fully trusted. Reference scheduled work uses the separately qualified guarded job dispatcher, not unscoped cron callbacks.'))
print('Native server actions preserve actor/scope with and without explicit groups; no workspace-scoped native crons; all fixtures rolled back')
