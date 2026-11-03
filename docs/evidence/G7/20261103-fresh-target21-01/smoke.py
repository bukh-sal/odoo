"""Actual fresh reference CRUD/composition/minimal Canvas and original-actor job."""
import json,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,LOCAL,f,context,snapshot,worker,prefix
from modular_platform.operator_os import protect_directory
from modular_platform.catalog import Catalog
from modular_platform.worker_operator import operator_observer
import r1_probe
PRIVATE=LOCAL/'fresh-smoke';PUBLIC=OUT/'fresh-smoke';f.OUTPUT=PUBLIC
state,native=context('connector');assert native.config['generation']==4
assert f.load(LOCAL/'reference-lifecycle/connector.json')['state']=='verified' and not PRIVATE.exists() and not PUBLIC.exists()
protect_directory(PRIVATE);PUBLIC.mkdir();marker=PRIVATE/'state.json';record=dict(state='starting',nonce=uuid4().hex);f.write(marker,record)
fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL
alice=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob')
before=snapshot(state,'fresh-smoke-before');assert before['mp_example_note']==before['mp_example_canvas_board']==before['mp_job']==[]
identity=worker(native,'fresh-smoke-worker-before');f.write(PRIVATE/'worker-before.json',identity)
observer=operator_observer(native.store,native.target_path);obs=observer.read();document=observer.state(obs,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
def binding(plugin,alias,workspace='A'):
 wid=fixture['workspaces'][workspace]['public_id'];inst=next(i['installation_id'] for i in document['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
 return next(b for b in document['bindings'] if b['consumer_installation_id']==inst and b['workspace_id']==wid and b['alias']==alias)
def call(client,plugin,alias,method,values,workspace='A',key=None,expect=200):
 b=binding(plugin,alias,workspace);body=dict(api_version=b['api_version'],request_id=str(uuid4()),input=values)
 if key:body['idempotency_key']=key
 code,response=client.request('/api/v1/services/'+b['service_id']+'/'+method,body,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':b['binding_id']});assert code==expect,(method,code,response.get('error',{}).get('code'))
 return response.get('data',response)
def phase(value):record['state']=value;f.write(marker,record)
views={}
for workspace in ('A','B'):
 v=alice.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options={}));assert '<list' in v['views']['list']['arch'] and '<form' in v['views']['form']['arch'];views[workspace]=sorted(v['views'])
phase('creating_A_note');body='Fresh reference\nمرحبا world\n'
a=alice.call('create',dict(title='Fresh release A',body=body),workspace='A',key=record['nonce']+'-A');record['A_note']=a;phase('A_note_created')
b=bob.call('create',dict(title='Fresh release B',body='Private B reference'),workspace='B',key=record['nonce']+'-B');record['B_note']=b;phase('B_note_created')
alice.call('create',dict(title='Viewer must not write'),workspace='B',key=record['nonce']+'-viewer',expect=403,code='FORBIDDEN')
alice.call('get',dict(note_id=b['id']),workspace='A',expect=404,code='NOT_FOUND');bob.call('get',dict(note_id=a['id']),workspace='B',expect=404,code='NOT_FOUND')
phase('setting_labels')
a=call(alice,'org.example.notes_labels','labels','set_labels',dict(note_id=a['id'],expected_revision=a['revision'],labels=['fresh','release']),key=record['nonce']+'-labels');assert a['revision']==2 and a['labels']==['fresh','release'];record['A_note']=a;phase('labels_saved')
v2=binding('org.example.canvas','documents');assert v2['api_version']=='2.0';projection=call(alice,'org.example.canvas','documents','get',dict(document_id=a['id']))
assert projection['document_id']==a['id'] and projection['content']==dict(headline=a['title'],text=body) and projection['revision']==2
phase('creating_minimal_canvas')
assert alice.native('search_count',args=[[]],workspace='A',model='mp.example.canvas.board')==0
alice.native('create',args=[dict(name='Minimal Canvas reference',cards=[])],workspace='A',model='mp.example.canvas.board')
board=call(alice,'org.example.canvas','boards','get',{});assert board['cards']==[] and board['revision']==1;record['board']=board;phase('canvas_created')
values=dict(board_id=board['id'],expected_revision=1,name=board['name'],cards=[dict(id=str(uuid4()),text='Reference card',lane='inbox',note_id=a['id'])])
saved=call(alice,'org.example.canvas','boards','save',values,key=record['nonce']+'-canvas');assert saved['revision']==2 and saved['cards']==values['cards']
assert call(alice,'org.example.canvas','boards','save',values,key=record['nonce']+'-canvas')==saved
conflict=call(alice,'org.example.canvas','boards','save',values,key=record['nonce']+'-canvas-stale',expect=409);assert conflict['error']['code']=='CONFLICT'
record['board']=saved;phase('canvas_saved_and_conflict_verified')
jobkey=record['nonce']+'-analysis';values=dict(note_id=a['id'],expected_revision=2)
enqueued=call(alice,'org.example.notes_stats','jobs','analyze',values,key=jobkey);assert enqueued['job']['state']=='pending';record['job_id']=enqueued['job']['id'];phase('analysis_enqueued')
assert call(alice,'org.example.notes_stats','jobs','analyze',values,key=jobkey)==enqueued
args=prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(LOCAL/'operator/worker-target.json'),'run-job-once'];phase('ordinary_runner_running')
runner=json.loads(f.command('fresh-smoke-run-once',args,timeout=240));f.save('runner.json',runner);phase('runner_terminal_needs_verification')
job=call(alice,'org.example.notes_stats','jobs','status',dict(note_id=a['id']))['job'];assert job['id']==record['job_id'] and job['state']=='completed' and job['attempts']==1 and job['error_code'] is None
expected=dict(characters=len(body),words=len(body.split()),lines=len(body.splitlines()));assert job['result']==dict(note_id=a['id'],revision=2,statistics=expected)
after=snapshot(state,'fresh-smoke-after');assert len(after['mp_example_note'])==2 and len(after['mp_example_canvas_board'])==1 and len(after['mp_job'])==1
assert len(after['mp_outbox'])==3 and len(after['mp_example_note_event_summary'])==0
assert worker(native,'fresh-smoke-worker-after')==identity
original=f.load(LOCAL/'original-preservation-query.json');current=json.loads(f.command('fresh-smoke-original-after',['docker','exec','-i',original['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',original['database'],'-v','ON_ERROR_STOP=1'],input=original['query'].encode()));assert current==original['expected'];f.guard(state)
f.save('qualified.json',dict(result='passed_actual_fresh_target21_reference_end_to_end',configuration_generation=4,host_image=native.config['image_id'],worker_image=identity['image'],native_Odoo_views=views,asymmetric_role_and_cross_workspace_denials=True,labels_write_revision2=True,named_v1_v2_binding_projection=True,minimal_canvas_empty_create_save_idempotent_stale_conflict=True,job_id=job['id'],original_actor='alice',job_attempts=1,statistics=expected,worker_process_image_key_mount_network_publication_exact=True,original_working17table_hashes_configs_exact=True,counts={t:len(rows) for t,rows in after.items()},browser_rendering=False,limits=['Fresh target reference integration only; final current acceptance/security/license/network/provenance/runbooks/performance/accessibility remain.','Canvas remains one minimal test board/card; standard Notes list/form uses native Odoo views.']))
phase('qualified');f.phase(state,'fresh_target21_reference_smoke_qualified');print('Actual fresh CRUD/Labels/v1-v2/minimalCanvas/ordinary original-actor worker job passed; original unchanged',flush=True)
