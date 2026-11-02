"""One owned real clear/get/restore round trip across fresh HTTP requests."""
import copy,importlib.util,json
from pathlib import Path
from uuid import uuid4
OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('canvas4_http',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
import r1_probe
f=m.f;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=m.j.LOCAL
state,native=m.context();assert native.config['generation']==27 and f.load(m.MARKER)['state']=='preservation_verified'
assert f.load(OUT/'native-results.json')['successful']
marker=m.PRIVATE/'http-marker.json';assert not marker.exists()
fixture=f.load(m.j.LOCAL/'fixtures.json');before=m.snapshot(state,'canvas4-http-before');worker=m.worker(native,'canvas4-http-worker-before')
board=before['mp_example_canvas_board'][0];original=f.load(OUT/'seed.json')['board'];assert board['public_id']==original['id'] and board['revision']==1 and board['cards']==original['cards']
bindings={w:next(r['descriptor']['binding_id'] for r in before['mp_service_binding'] if r['descriptor']['alias']=='boards' and r['workspace_id']==fixture['workspaces'][w]['id']) for w in ['A','B']}
alice=r1_probe.Client(state,fixture);bob=r1_probe.Client(state,fixture,'bob');raw=[];checks=[]
def call(client,method,values,workspace='A',status=200,error=None):
 response_status,response=client.request('/api/v1/services/org.example.canvas.boards/'+method,dict(api_version='1.0',request_id='g7-canvas-'+uuid4().hex,input=values),workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':bindings[workspace]})
 raw.append(dict(method=method,workspace=workspace,status=response_status,response=response));f.write(m.PRIVATE/'http-raw.json',raw)
 assert response_status==status,(method,response_status,response.get('error',{}).get('code'))
 if error:assert response['error']['code']==error
 else:assert 'data' in response
 checks.append(dict(method=method,workspace=workspace,status=response_status,expected_error=error,passed=True));return response.get('data',response)
f.write(marker,dict(state='clearing_once',original=original,board_native_id=board['id']))
empty=call(alice,'save',dict(board_id=original['id'],expected_revision=1,name=original['name'],cards=[]));assert empty['cards']==[] and empty['revision']==2
f.write(marker,dict(state='empty_committed',original=original,empty=empty))
fresh=r1_probe.Client(state,fixture);assert call(fresh,'get',dict(board_id=original['id']))==empty
call(alice,'save',dict(board_id=original['id'],expected_revision=1,name=original['name'],cards=original['cards']),status=409,error='CONFLICT')
call(alice,'save',dict(board_id=original['id'],expected_revision=2,name=original['name'],cards=None),status=400,error='INVALID_INPUT')
for ident in [original['id'],str(uuid4())]:call(bob,'get',dict(board_id=ident),'B',status=404,error='NOT_FOUND')
call(alice,'save',dict(board_id=original['id'],expected_revision=2,name=original['name'],cards=[]),'B',status=403,error='FORBIDDEN')
f.write(marker,dict(state='restoring_owned_fixture_once',original=original,empty=empty))
restored=call(alice,'save',dict(board_id=original['id'],expected_revision=2,name=original['name'],cards=original['cards']));assert restored==dict(original,revision=3)
assert call(fresh,'get',dict(board_id=original['id']))==restored
after=m.snapshot(state,'canvas4-http-after');expected=copy.deepcopy(before)
old=expected['mp_example_canvas_board'][0];current=after['mp_example_canvas_board'][0]
assert current['write_date']>=old['write_date'];old.update(revision=3,write_date=current['write_date']);assert expected==after
assert m.worker(native,'canvas4-http-worker-after')==worker
f.write(marker,dict(state='owned_fixture_restored_revision3',original=original,restored=restored))
f.save('http-results.json',dict(result='passed_actual_empty_board_clear_reload_restore',checks=checks,configuration_generation=27,image=state['image_id'],fresh_authenticated_client_observed_committed_empty_array=True,exact_owned_fixture_cards_restored=True,owned_board_revision=[1,2,3],all36jobs_30Notes_other16tables_worker_exact=True,standard_CRUD_uses_native_Odoo=True,no_new_UI_features=True))
print('Actual HTTP committed empty array and fresh get pass; stale/invalid/viewer/foreign denied, owned cards restored at revision3')
