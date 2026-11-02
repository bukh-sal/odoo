"""The shared native guard also protects Canvas and its Note references."""
import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('core20_current',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f,j=m.f,m.j;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==28
before=m.snapshot(state,'g7-window2-canvas-02-native-before')
code="""import json,uuid
from odoo import api
from odoo.exceptions import AccessError,MissingError
from odoo.addons.mp_identity.scopes import scoped_environment
env.cr.rollback()
def actor(user,workspace):return scoped_environment(api.Environment(env.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
checks=[]
try:
 a=actor('alice','A');b=actor('bob','B');viewer=actor('alice','B')
 own=a['mp.example.canvas.board'].search([],limit=1);assert own and own.revision==3
 original_cards=own.cards;original_revision=own.revision
 other=b['mp.example.canvas.board'].create({'name':'ID03 temporary Canvas B','cards':[dict(id=str(uuid.uuid4()),text='Minimal fixture card',lane='inbox',note_id=None)]})
 assert own.web_read({'id':{}})==[{'id':own.id}]
 assert viewer['mp.example.canvas.board'].browse(other.id).web_read({'id':{}})==[{'id':other.id}]
 for ids in [[other.id],[own.id,other.id],[2147483647]]:
  try:a['mp.example.canvas.board'].browse(ids).web_read({})
  except AccessError:pass
  else:raise AssertionError('Canvas native read bypassed scope')
 try:viewer['mp.example.canvas.board'].browse(other.id).with_context(expected_revision=1).write({'name':'Denied viewer update'})
 except AccessError:pass
 else:raise AssertionError('Canvas viewer wrote')
 checks.append('actual Canvas id-only/empty native reads and viewer write enforce current workspace/role')
 env.cr.execute('SELECT public_id FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces']['A']['id']]);note=env.cr.fetchone()[0]
 env.cr.execute('SELECT public_id FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces']['B']['id']]);foreign=env.cr.fetchone()[0]
 card=dict(id=str(uuid.uuid4()),text='Scoped Note reference',lane='inbox',note_id=note)
 own.with_context(expected_revision=original_revision).write({'cards':[card]});assert own.revision==original_revision+1
 for ident in [foreign,str(uuid.uuid4())]:
  try:
   with env.cr.savepoint():own.with_context(expected_revision=original_revision+1).write({'cards':[dict(card,note_id=ident)]})
  except MissingError:pass
  else:raise AssertionError('Foreign/missing Note reference accepted')
  assert own.revision==original_revision+1 and own.cards==[card]
 checks.append('actual Canvas JSON Note references accept own and reject foreign/missing identically with savepoint rollback')
finally:env.cr.rollback();env.invalidate_all()
print('MP_CANVAS_PATHS='+json.dumps(dict(result='passed',checks=checks,all_board_fixtures_rolled_back=True,product_features_added=False)))
""".replace('FIXTURE',repr(f.load(j.LOCAL/'fixtures.json')))
raw=f.native(state,'g7-window2-canvas-paths-02',[],code)
rows=[json.loads(line.split('MP_CANVAS_PATHS=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CANVAS_PATHS=')];assert len(rows)==1
assert m.snapshot(state,'g7-window2-canvas-02-native-after')==before
f.save('canvas-paths.json',dict(**rows[0],native_generation=28,image=state['image_id'],all36jobs_other16tables_exact=True))
print('Canvas native scope/role and Note-reference boundaries pass; temporary boards rolled back, no product expansion')
