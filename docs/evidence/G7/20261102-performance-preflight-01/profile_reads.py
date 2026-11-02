"""Measure actual installed query counts; no monkeypatch/source replacement."""
import importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('profile_read_current',OUT.parent/'20261102-canvas4-source-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==27
before=m.snapshot(state,'perf-query-profile-before')
code="""import json,time
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment,current_scope
from odoo.addons.mp_core.dispatch import CallFrame,call_bound
env.cr.rollback()
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
scope=actor.context['_mp_scope'];binding=FIXTURE['bindings']['A']
actor=actor(context={**actor.context,'_mp_call_frame':CallFrame(scope.principal_public_id,scope.workspace_public_id,FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())})
notes=actor['mp.example.note'].search([],order='id');assert len(notes)==24
operations=[('current_scope',lambda:current_scope(actor)),('whole_recordset_guard',lambda:notes._mp_guard('read')),('one_warmed_scalar',lambda:notes[0].title),
 ('native_list24',lambda:actor['mp.example.note'].web_search_read([],specification={k:{} for k in ['title','revision','write_date','x_notes_labels']},limit=80)),
 ('native_detail',lambda:notes[0].web_read({k:{} for k in ['title','body','revision','x_notes_labels']})),
 ('gateway_list24',lambda:call_bound(actor,'documents','list',{'limit':25})),('gateway_detail',lambda:call_bound(actor,'documents','get',{'note_id':notes[0].public_id}))]
results=[]
for name,operation in operations:
 operation() # warm native metadata/field caches first
 samples=[]
 for _ in range(3):
  queries=env.cr.sql_log_count;started=time.perf_counter();operation();elapsed=(time.perf_counter()-started)*1000
  samples.append(dict(ms=elapsed,sql_queries=env.cr.sql_log_count-queries))
 results.append(dict(operation=name,samples=samples))
env.cr.rollback();env.invalidate_all()
print('MP_READ_PROFILE='+json.dumps(dict(results=results,actual_installed_source=True,no_monkeypatch=True,no_data_writes=True)))
""".replace('FIXTURE',repr(f.load(m.j.LOCAL/'fixtures.json')))
raw=f.native(state,'g7-query-profile-01',[],code)
rows=[json.loads(line.split('MP_READ_PROFILE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_READ_PROFILE=')];assert len(rows)==1
assert m.snapshot(state,'perf-query-profile-after')==before
f.save('query-profile.json',dict(result='actual_installed_read_query_counts',**rows[0],image=state['image_id'],all17tables_exact=True,limits='Single native rollback-only profiling process with warm caches; not HTTP or10k qualification.'))
print(json.dumps(rows[0]))
