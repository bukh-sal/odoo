"""Minimal G5 reference-fixture acceptance, with one explicit saved revision per board."""
import json
from uuid import uuid4
from clean_recovery_fixture import LOCAL, OUTPUT, load, write, save, guard
from clean_recovery_data import context, call, board
from clean_recovery_http import Client
from lifecycle_data_probe import BUSINESS_SQL, sql

state,target,reader,document,fixture=context()
assert state['phase']=='restored_resumed'
marker=LOCAL/'canvas-reference-qualification.json'; assert not marker.exists()
assert load(OUTPUT/'closed-preservation.json')['result']=='passed'
before=json.loads(sql(reader,BUSINESS_SQL))
assert before==load(OUTPUT/'business-before-fault.json')
record=dict(state='running',run_id=str(uuid4()),completed=[]);write(marker,record)
for space,actor in [('A','alice'),('B','bob')]:
    board(space)  # Same explicit provisioning command verifies its marker; never duplicates.
    client=Client(state,fixture,actor,'alice-new-password' if actor=='alice' else 'bootstrap-password')
    previous=call(client,document,fixture,'org.example.canvas','boards','get',{},space)
    values=dict(board_id=previous['id'],expected_revision=previous['revision'],name=previous['name'],cards=previous['cards'])
    record['pending']=dict(workspace=space,expected_revision=previous['revision'],idempotency_key=record['run_id']+'-'+space);write(marker,record)
    updated=call(client,document,fixture,'org.example.canvas','boards','save',values,space,key=record['pending']['idempotency_key'])
    assert updated==dict(previous,revision=previous['revision']+1)
    assert call(client,document,fixture,'org.example.canvas','boards','save',values,space,key=record['pending']['idempotency_key'])==updated
    conflict=call(client,document,fixture,'org.example.canvas','boards','save',values,space,key=record['pending']['idempotency_key']+'-stale',expect=409)
    assert conflict['error']['code']=='CONFLICT'
    assert call(client,document,fixture,'org.example.canvas','boards','get',{},space)==updated
    foreign=load(LOCAL/('reference-board-'+('B' if space=='A' else 'A')+'.json'))['board']['public_id']
    missing=call(client,document,fixture,'org.example.canvas','boards','get',dict(board_id=foreign),space,expect=404)
    assert missing['error']['code']=='NOT_FOUND'
    assert client.native('search_count',[[]],workspace=space,model='mp.example.canvas.board')==1
    record['completed'].append(dict(workspace=space,revision_before=previous['revision'],revision_after=updated['revision'],one_board=True,repeat_provision_no_duplicate=True,save_idempotent=True,stale_conflict=True,foreign_board_not_found=True))
    record.pop('pending');write(marker,record)
after=json.loads(sql(reader,BUSINESS_SQL))
for key in ['notes','features','bindings','grants']:assert before[key]==after[key]
for old,new in zip(before['boards'],after['boards']):
    assert new['revision']==old['revision']+1
    assert {k:v for k,v in new.items() if k not in ['revision','write_date']}=={k:v for k,v in old.items() if k not in ['revision','write_date']}
record['state']='completed_verified';write(marker,record);save('minimal-Canvas-fixture.json',dict(result='passed',fresh_provisioning='clean_recovery_data.py board --workspace A|B after actual empty-core initialization and independently approved packaged install',checks=record['completed'],application_changes='Only the required two test saves, revision1→2; cards/name/content unchanged.',UI_or_product_feature_expansion=False,lifecycle_regression='Actual checkpoint, destructive Labels native uninstall/failure, fresh restore and separately approved resume preserved both boards exactly before these explicit saves. Prior Canvas suspension/removal gating evidence remains current; Canvas source/image unchanged.'))
save('business-after-reference-tests.json',after);guard(state)
print(json.dumps(dict(result='passed_minimal_reference_fixture',boards=2,revision_advances=2)))
