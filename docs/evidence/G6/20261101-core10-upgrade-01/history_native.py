"""Real core10 retained envelopes, replay and native consumer dedup; rollback."""
import hashlib,json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import durable,event_store,dispatch_lifecycle as LC
env.cr.rollback();assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=env.cr.fetchone()[0]
scope=LC.LifecycleScope(FIXTURE['site_id'],release);baseline=LC.observe(env.cr,scope)
def table(name):
    env.cr.execute("SELECT count(*),encode(sha256(convert_to(COALESCE(string_agg(to_jsonb(t)::text,'' ORDER BY id),''),'UTF8')),'hex') FROM "+name+' t');return env.cr.fetchone()
projection=table('mp_example_note_event_summary');notes=table('mp_example_note')
def actor(workspace):return scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
def call(native,kind,**values):return events.dispatch(native,dict(protocol=1,kind=kind+'_request',request_id=str(uuid4()),**values))
native=actor('C')
sub=events.dispatch(native,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=FIXTURE['bindings']['C']['binding_id'])['subscription_id']
expected=next(e for e in SEED['history'] if e['aggregate_id']==SEED['prior_note'] and e['aggregate_sequence']==1)
assert expected['release_digest']!=release
batch=call(native,'poll',subscription_id=sub,limit=50)['deliveries'];target=next(d for d in batch if d['event']['id']==expected['public_id'])
assert target['event']['payload']==expected['payload'] and target['event']['aggregate_id']==expected['aggregate_id'] and target['event']['schema_version']==expected['schema_version']
receipt=dict(delivery_id=target['id'],receipt=target['receipt'],generation=target['generation'])
assert call(native,'ack',subscription_id=sub,receipts=[receipt])['acknowledged']==[target['id']]
assert call(native,'replay',subscription_id=sub,event_ids=[expected['public_id']])['replayed']==[target['id']]
again=call(native,'poll',subscription_id=sub,limit=50)['deliveries'];assert any(d['event']['id']==expected['public_id'] for d in again)
env.cr.execute('SELECT to_jsonb(o) FROM mp_outbox o WHERE public_id=%s',[expected['public_id']]);assert env.cr.fetchone()[0]==expected
b=actor('B');foreign=events.dispatch(b,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=FIXTURE['bindings']['B']['binding_id'])['subscription_id']
try:call(b,'replay',subscription_id=foreign,event_ids=[expected['public_id']]);raise AssertionError('Foreign historical event replay allowed')
except PublicError as error:assert error.code=='NOT_FOUND'
# Reuse a real retained consumption tombstone through the actual native
# consumer hook, not only a direct uniqueness query or a fabricated row.
a=actor('A');handler='org.example.notes_labels:revision_projection'
env.cr.execute("SELECT b.public_id FROM mp_service_binding b JOIN mp_plugin_installation i ON i.id=b.consumer_id WHERE i.plugin_id='org.example.notes_labels' AND b.workspace_id=%s AND b.alias='documents' AND b.state='active'",[FIXTURE['workspaces']['A']['id']]);binding=env.cr.fetchone()[0]
env.cr.execute('SELECT o.public_id FROM mp_event_consumption c JOIN mp_outbox o ON o.id=c.event_id WHERE c.workspace_id=%s AND c.handler=%s ORDER BY c.id LIMIT 1',[FIXTURE['workspaces']['A']['id'],handler]);old_consumed=env.cr.fetchone()[0]
consumer=events.dispatch(a,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=binding)['subscription_id']
for ignored in range(50):
    _,subscription,_=events._subscription(a,consumer,active=True)
    candidate=event_store.candidates(env.cr,subscription,1);assert candidate
    if candidate[0]['public_id']==old_consumed:break
    item=call(a,'poll',subscription_id=consumer,limit=1)['deliveries'][0]
    call(a,'ack',subscription_id=consumer,receipts=[dict(delivery_id=item['id'],receipt=item['receipt'],generation=item['generation'])])
else:raise AssertionError('Retained tombstone event not reached in bounded current authorized history')
duplicate=events.consume_registered(a,consumer,handler);assert duplicate==dict(state='duplicate',event_id=old_consumed)
assert table('mp_example_note_event_summary')==projection
assert LC.observe(env.cr,scope)['tables']['mp_event_consumption']==baseline['tables']['mp_event_consumption']
durable.set_control(env.cr,FIXTURE['site_id'],release,'paused')
assert call(native,'close',subscription_id=sub)['closed'] and call(native,'close',subscription_id=sub)['closed']
assert call(native,'status',subscription_id=sub)['state']=='closed'
env.cr.rollback();env.invalidate_all();assert LC.observe(env.cr,scope)==baseline and table('mp_example_note_event_summary')==projection and table('mp_example_note')==notes;env.cr.rollback()
print('MP_CORE10_HISTORY='+json.dumps(dict(result='passed_installed_core10_history_replay_and_native_dedup',retained_old_release_event_delivered_and_replayed=True,original_producer_envelope_exact=True,current_scope_foreign_replay_denied=True,actual_native_consumer_retained_tombstone_returns_duplicate=True,projection_and_consumption_history_not_duplicated=True,paused_close_idempotent_and_status_safe=True,all_subscription_receipt_policy_changes_rolled_back=True,source_substitution=False)))
