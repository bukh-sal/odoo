"""Current candidate keeps native CRUD/views and private scheduler ACLs."""
import json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_job_fixture as j
j.select_profile('runner');f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='job_processes_and_kernel_verified'
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL
fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture)
query="SELECT jsonb_build_object('mp.job',(SELECT min(id) FROM mp_job),'mp.outbox',(SELECT min(id) FROM mp_outbox),'mp.dispatch.control',(SELECT min(id) FROM mp_dispatch_control));"
ids=json.loads(f.sql(state,'HTTP-private-ids',query));assert all(ids.values())
cases=[]
for model,ident in ids.items():
    for method,args in [('read',[[ident]]),('create',[{}]),('write',[[ident],{'state':'completed'}]),('unlink',[[ident]])]:
        client.native(method,args,model=model,deny=True);cases.append(dict(model=model,method=method,result='AccessError'))
for actor,workspace in [('alice','A'),('alice','B'),('bob','B')]:
    reader=client if actor=='alice' else r1_probe.Client(state,fixture,actor)
    result=reader.native('get_views',kwargs={'views':[[False,'list'],[False,'form']],'options':{'toolbar':False}},workspace=workspace)
    assert {'list','form'}<=set(result['views'])
created=client.call('create',dict(title='Current runner image HTTP CRUD '+uuid4().hex,body='Synthetic owned proof'),key=uuid4().hex)
assert client.call('get',dict(note_id=created['id']))==created
updated=client.call('update',dict(note_id=created['id'],expected_revision=1,title='Updated native service proof'),key=uuid4().hex)
assert updated['revision']==2
client.call('update',dict(note_id=created['id'],expected_revision=1,title='Rejected stale edit'),expect=409,code='CONFLICT')
client.call('delete',dict(note_id=created['id'],expected_revision=2),key=uuid4().hex)
client.call('get',dict(note_id=created['id']),expect=404,code='NOT_FOUND')
f.guard(state)
path=OUT/'HTTP-native-regression.json';assert not path.exists()
f.write(path,dict(result='passed',image_id=state['image_id'],inventory_digest=state['inventory_digest'],private_CRUD_denials=cases,native_list_form_contexts=['Alice A administrator','Alice B viewer','Bob B editor'],current_gateway_create_get_update_delete_and_CAS=True,only_new_suite_owned_note_deleted=True,Canvas_or_frontend_changes=False))
print(json.dumps(dict(result='passed',private_CRUD_denials=len(cases),native_view_contexts=3,current_CRUD=True)))
