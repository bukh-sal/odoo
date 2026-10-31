"""Actual new registry/API wiring, entirely rolled back before qualification."""
import json,sys,traceback
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events

cr=ENV.cr;cr.rollback();fixture=FIXTURE
assert cr.dbname.startswith('mp_disposable_r0_r1_g6_')
space=fixture['workspaces']['A'];actor=fixture['users']['alice']
native=scoped_environment(api.Environment(cr,actor['id'],{}),space['public_id'])
tables=['mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_example_note','mp_example_note_event_summary']


def counts(cursor):
    result={}
    for table in tables:
        cursor.execute('SELECT count(*) FROM '+table);result[table]=cursor.fetchone()[0]
    return result


def call(operation,**values):
    return events.dispatch(native,dict(protocol=1,kind=operation+'_request',request_id=str(uuid4()),**values))


def subscribe(plugin):
    cr.execute("SELECT b.public_id FROM mp_service_binding b JOIN mp_plugin_installation i ON i.id=b.consumer_id WHERE i.plugin_id=%s AND b.workspace_id=%s AND b.alias='documents' AND b.state='active'",[plugin,space['id']])
    return events.dispatch(native,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=cr.fetchone()[0])['subscription_id']


baseline=counts(cr);assert all(number==0 for number in baseline.values())
checks=[];success=False
try:
    own=subscribe('org.example.notes');labels=subscribe('org.example.notes_labels')
    note=native['mp.example.note'].create(dict(title='Rollback-only event smoke',body='Synthetic private content'))
    public_id=note.public_id;native.flush_all()
    batch=call('poll',subscription_id=own,limit=50);assert len(batch['deliveries'])==1
    item=batch['deliveries'][0];assert item['event']['payload']==dict(note_id=public_id,revision=1,change='created')
    assert set(item['event']['payload'])=={'note_id','revision','change'};checks.append('actual producer and strict minimized API envelope')
    with ENV.registry.cursor() as other:
        assert all(number==0 for number in counts(other).values())
    checks.append('second actual connection sees no uncommitted producer/subscription/effect')
    receipt=dict(delivery_id=item['id'],receipt=item['receipt'],generation=item['generation'])
    assert call('ack',subscription_id=own,receipts=[receipt])['acknowledged']==[item['id']]
    assert call('ack',subscription_id=own,receipts=[receipt])['acknowledged']==[item['id']]
    checks.append('same current receipt acknowledgement is idempotent')
    result=events.consume_registered(native,labels,'org.example.notes_labels:revision_projection');assert result['state']=='applied',result
    summary=native['mp.example.note.event.summary'].search([('note_id','=',public_id)])
    assert len(summary)==1 and summary.event_count==summary.last_revision==1 and summary.create_uid.id==actor['id']
    checks.append('registered original-user native projection/tombstone/ACK')
    call('replay',subscription_id=labels,event_ids=[item['event']['id']])
    result=events.consume_registered(native,labels,'org.example.notes_labels:revision_projection');assert result['state']=='duplicate',result
    summary.invalidate_recordset();assert summary.event_count==1
    checks.append('explicit replay cannot duplicate native effect')
    note.with_context(expected_revision=1).write(dict(title='Updated rollback-only smoke'))
    # The existing raw-SQL unlink preflight does not flush a pending revision.
    # Keep that separately recorded required R1 defect open. This event-history
    # smoke needs a stored revision, as ordinary committed CRUD requests have.
    native.flush_all()
    note.with_context(expected_revision=2).unlink()
    batch=call('poll',subscription_id=own,limit=50)
    assert [d['event']['payload']['change'] for d in batch['deliveries']]==['updated','deleted']
    assert [d['event']['aggregate_sequence'] for d in batch['deliveries']]==[2,3]
    checks.append('retained minimized history survives deletion of current record')
    with cr.savepoint():
        try:native['mp.example.note.event.summary'].create(dict(note_id=public_id,installation_id=1,event_count=99,last_revision=99))
        except AccessError:pass
        else:raise AssertionError('Untyped caller created native projection')
    checks.append('native projection cannot be created without typed consumer frame')
    success=True
except Exception:
    traceback.print_exc(file=sys.stderr)
finally:
    cr.rollback()
after=counts(cr);assert after==baseline,'Unexpected committed smoke mutation'
print('MP_EVENT_SMOKE='+json.dumps(dict(successful=success,checks=checks,all_business_event_and_receipt_rows_rolled_back=True,counts_after=after)))
cr.rollback();raise SystemExit(0 if success else 1)
