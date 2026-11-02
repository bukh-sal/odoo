"""Discriminate warmed scalar cache behavior on the installed immutable image."""
import importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('cache_current',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f,j=m.f,m.j;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==25
before=m.snapshot(state,'g7-cache-01-before')
code="""import json
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
env.cr.rollback()
def actor(user,workspace):return scoped_environment(api.Environment(env.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
results=[]
try:
 a=actor('alice','A')
 env.cr.execute('SELECT id FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces']['A']['id']]);ident=env.cr.fetchone()[0]
 own=a['mp.example.note'].browse(ident);expected=own.body
 assert isinstance(expected,str) and expected
 for user,workspace in [('alice','B'),('bob','B')]:
  other=actor(user,workspace)['mp.example.note'].browse(ident)
  try:other.read(['body'])
  except AccessError:guard_denied=True
  else:raise AssertionError('ordinary read unexpectedly allowed')
  try:observed=other.body
  except AccessError:denied=True;matches=False
  else:denied=False;matches=observed==expected
  results.append(dict(user=user,workspace=workspace,ordinary_read_denied=guard_denied,scalar_denied=denied,warmed_foreign_value_returned=matches))
finally:env.cr.rollback();env.invalidate_all()
print('MP_CACHE_PROBE='+json.dumps(dict(results=results,fixture_writes=False)))
""".replace('FIXTURE',repr(f.load(j.LOCAL/'fixtures.json')))
raw=f.native(state,'g7-cache-probe-01',[],code)
rows=[json.loads(line.split('MP_CACHE_PROBE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CACHE_PROBE=')];assert len(rows)==1
assert m.snapshot(state,'g7-cache-01-after')==before
f.save('cache-counterexample.json',dict(**rows[0],native_generation=25,image=state['image_id'],all36jobs_other16tables_exact=True,trust_boundary='Cooperating native ORM callers; not a demonstrated HTTP leak or sandbox claim'))
print(json.dumps(rows[0]))
