"""Minimal populated OPS02 data; optional Canvas remains a reference fixture.

No attachment support is added to Notes/Canvas. The binary is a native global
operator-owned attachment, solely to verify the database/filestore runbook.
"""
import argparse,base64,hashlib,json,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from clean_recovery_fixture import ROOT,LOCAL,OUTPUT,load,write,save,phase,guard
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_release_reader_rollout import files
import r1_probe

PAYLOAD=b'OPS02 synthetic private native attachment\n'+bytes(range(256))*32

def context():
 state=load(LOCAL/'state.json');guard(state);target=load(LOCAL/'operator/target.json');reader=DockerObserver(target);catalog=Catalog(LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'),readonly=True);document=reader.state(reader.read(),catalog.snapshot())['state'];fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;return state,target,reader,document,fixture

def call(client,document,fixture,plugin,alias,method,values,workspace,key=None,expect=200):
 wid=fixture['workspaces'][workspace]['public_id'];installation=next(i['installation_id'] for i in document['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid);binding=next(b for b in document['bindings'] if b['consumer_installation_id']==installation and b['workspace_id']==wid and b['alias']==alias);payload=dict(api_version=binding['api_version'],request_id=str(uuid4()),input=values)
 if key:payload['idempotency_key']=key
 status,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']});assert status==expect,(status,value.get('error',{}).get('code'));return value.get('data',value)

def seed():
 state,target,reader,document,fixture=context();marker=LOCAL/'recovery-data.json';assert state['phase']=='references_installed' and not marker.exists();assert json.loads(sql(reader,'SELECT jsonb_build_array((SELECT count(*) FROM mp_example_note),(SELECT count(*) FROM mp_example_canvas_board));'))==[0,0];record=dict(phase='seeding',run_id=str(uuid4()),notes={});write(marker,record);phase(state,'seeding_recovery_notes')
 for workspace,actor in [('A','alice'),('B','bob')]:
  client=r1_probe.Client(state,fixture,actor);record['notes'][workspace]=[]
  for index in range(2):
   note=client.call('create',dict(title='Recovery '+workspace+'/'+str(index),body='Minimal retained reference data.'),workspace,key=record['run_id']+'-note-'+workspace+str(index));record['notes'][workspace].append(note);write(marker,record)
   if index==0:record['notes'][workspace][-1]=call(client,document,fixture,'org.example.notes_labels','labels','set_labels',dict(note_id=note['id'],expected_revision=note['revision'],labels=['recovery',workspace.lower()]),workspace,key=record['run_id']+'-labels-'+workspace);write(marker,record)
  views=client.native('get_views',kwargs={'views':[(False,'list'),(False,'form')],'options':{}},workspace=workspace);assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
 operator=r1_probe.Client(state,fixture,'operator');record['pending_nonretryable']='native global attachment create';write(marker,record);attachment=operator.native('create',[dict(name='OPS02 native private recovery proof.bin',type='binary',datas=base64.b64encode(PAYLOAD).decode(),mimetype='application/octet-stream',public=False)],model='ir.attachment');record['attachment_id']=attachment;record.pop('pending_nonretryable');write(marker,record)
 req=urllib.request.Request(operator.base+'/web/content/'+str(attachment)+'?download=1',headers={'X-MP-Client-Release':operator.release_token})
 with operator.http.open(req,timeout=30) as response:data=response.read();assert response.status==200 and data==PAYLOAD
 record.update(phase='notes_and_attachment_seeded',attachment_sha256=hashlib.sha256(PAYLOAD).hexdigest(),attachment_bytes=len(PAYLOAD),schema=json.loads(sql(reader,SCHEMA)));write(marker,record);phase(state,'notes_attachment_ready');save('notes-attachment-baseline.json',record);print(json.dumps(dict(result='passed',notes=4,native_private_attachment=1,standard_views='native Odoo')))

def board(workspace):
 state,target,reader,document,fixture=context();assert state['phase'] in ['notes_attachment_ready','reference_boards_ready','restored_resumed'];record=load(LOCAL/'recovery-data.json');assert record['phase']=='notes_and_attachment_seeded';marker=LOCAL/('reference-board-'+workspace+'.json');actor='alice' if workspace=='A' else 'bob'
 if state['phase']=='restored_resumed':
  assert marker.exists(),'Restored verification must not create a replacement reference board'
  from clean_recovery_http import Client
  client=Client(state,fixture,actor,'alice-new-password' if actor=='alice' else 'bootstrap-password')
 else:client=r1_probe.Client(state,fixture,actor)
 if marker.exists():
  previous=load(marker);assert previous['phase']=='completed_verified','Reconcile pending non-idempotent create; never blindly reseed';current=call(client,document,fixture,'org.example.canvas','boards','get',{},workspace);assert current['id']==previous['board']['public_id'];print(json.dumps(dict(result='existing_reference_verified',workspace=workspace,no_duplicate_create=True)));return
 assert client.native('search_count',[[]],workspace=workspace,model='mp.example.canvas.board')==0;pending=dict(phase='creating_once',workspace_id=fixture['workspaces'][workspace]['public_id'],actor=actor,name='Recovery reference '+workspace);write(marker,pending);ident=client.native('create',[dict(name=pending['name'],cards=[dict(id=str(uuid4()),text='Minimal reference card',lane='inbox',note_id=record['notes'][workspace][0]['id'])])],workspace=workspace,model='mp.example.canvas.board');pending.update(phase='created_needs_read',native_id=ident);write(marker,pending);current=client.native('read',[[ident],['public_id','name','revision','cards']],workspace=workspace,model='mp.example.canvas.board')[0];dto=call(client,document,fixture,'org.example.canvas','boards','get',{},workspace);assert current['public_id']==dto['id'] and len(dto['cards'])==1;pending.update(phase='completed_verified',board=current);write(marker,pending);save('reference-board-'+workspace+'.json',pending)
 if all((LOCAL/('reference-board-'+s+'.json')).exists() and load(LOCAL/('reference-board-'+s+'.json'))['phase']=='completed_verified' for s in ['A','B']):
  phase(state,'reference_boards_ready');save('business-before-fault.json',json.loads(sql(reader,BUSINESS_SQL)));save('schema-before-fault.json',json.loads(sql(reader,SCHEMA)));save('files-before-fault.json',files(reader));save('state-before-fault.json',document)
 print(json.dumps(dict(result='reference_board_provisioned',workspace=workspace,cards=1,normal_native_workspace_authority=True)))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['seed','board']);parser.add_argument('--workspace',choices=['A','B']);args=parser.parse_args()
 if args.action=='seed':assert not args.workspace;seed()
 else:assert args.workspace;board(args.workspace)
