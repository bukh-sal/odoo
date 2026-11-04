"""Read-only installed native views and scoped HTTP after core23 maintenance."""
import json
from pathlib import Path
import sys

ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT))
import activate as m
import r1_probe

f=m.f;f.OUTPUT=OUT;state,native=m.context('connector');r=f.load(m.PRIVATE/'state.json')
assert native.config['generation']==6 and r['state']=='preservation_verified'
fixture=f.load(m.LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=m.LOCAL
alice=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob')
before=m.snapshot(state,'core23-http-before');identity=m.worker(native,'core23-http-worker-before')
for client,workspace in [(alice,'A'),(bob,'B')]:
    data=client.call('list',dict(limit=25),workspace);assert len(data['items'])==1
    views=client.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options={}))
    assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
foreign=bob.call('list',dict(limit=25),'B')['items'][0]
alice.call('get',dict(note_id=foreign['id']),expect=404,code='NOT_FOUND')
assert m.snapshot(state,'core23-http-after')==before and m.worker(native,'core23-http-worker-after')==identity
f.guard(state)
f.save('http.json',dict(result='passed_current_core23_native_list_form_scope_HTTP',image_id=r['image_id'],
    configuration_generation=6,actors=2,workspaces=2,all17tables_worker_exact=True,
    limits=['Read-only native view/API checks; app manager uninstall request, actual uninstall and recovery remain required. No rendered browser or performance/accessibility credit.']))
r['state']='backend_qualified_native_uninstall_pending';f.write(m.PRIVATE/'state.json',r)
f.phase(state,'core23_backend_qualified');print('Core23 actual native list/form and scoped read HTTP pass; no data mutations')
