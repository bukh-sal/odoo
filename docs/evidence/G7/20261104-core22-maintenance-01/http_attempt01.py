"""Current installed HTTP/native defaults and one exactly tracked temporary note."""
import json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT));import activate as m
import r1_probe
f=m.f;f.OUTPUT=OUT;state,native=m.context('connector');r=f.load(m.PRIVATE/'state.json');assert native.config['generation']==5 and r['state']=='preservation_verified'
fixture=f.load(m.LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=m.LOCAL;alice=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob');before=m.snapshot(state,'core22-http-before');identity=m.worker(native,'core22-http-worker-before')
checks=[]
for client,workspace in [(alice,'A'),(bob,'B')]:
 data=client.call('list',dict(limit=25),workspace);assert len(data['items'])==1
 views=client.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options={}));assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
checks.append('actual_new_client_release_native_list_form_and_scoped_reads')
foreign=bob.call('list',dict(limit=25),'B')['items'][0];alice.call('get',dict(note_id=foreign['id']),expect=404,code='NOT_FOUND');checks.append('foreign_workspace_note_hidden')
marker=m.PRIVATE/'http-state.json';assert not marker.exists();record=dict(state='creating',key='core22-'+uuid4().hex);f.write(marker,record)
values=dict(title='Core22 owned HTTP probe',body='Temporary qualified CRUD record')
created=alice.call('create',values,key=record['key']);record.update(state='created',note=created);f.write(marker,record)
assert alice.call('create',values,key=record['key'])==created;checks.append('valid_CSRF_mutation_and_same_key_replay_one_record')
deleted=alice.call('delete',dict(note_id=created['id'],expected_revision=created['revision']),key=record['key']+'-delete');assert deleted['deleted'];record['state']='deleted_verified';f.write(marker,record)
checks.append('exact_owned_temporary_record_deleted')
after=m.snapshot(state,'core22-http-after')
for table,rows in before.items():
 if table=='mp_outbox':
  assert after[table][:len(rows)]==rows and len(after[table])==len(rows)+2
  new=after[table][len(rows):];assert all(e['aggregate_id']==created['id'] for e in new)
 else:assert after[table]==rows,table
assert m.worker(native,'core22-http-worker-after')==identity;f.guard(state)
f.save('http.json',dict(result='passed_installed_core22_HTTP_native_views_scope_and_owned_CRUD',image_id=r['image_id'],configuration_generation=5,checks=checks,temporary_record_removed=True,new_outbox_events=2,old17table_rows_worker_configs_preserved=True,limits=['Same-key replay smoke only, not full API05concurrency/server-crash requalification.','Unchanged native shell/services/UI source; no browser rendering/accessibility or global HTTP security/load requalification claim.']))
print(json.dumps(dict(result='core22_HTTP_passed',checks=len(checks),temporary_note_removed=True,expected_outbox_events=2)))
