"""Exercise reviewed event retention, native effects and expired replay."""

from datetime import datetime, timedelta, timezone
import json
import sys
from uuid import uuid4

from background_lifecycle import shell
from background_site import load, write
from background_workers import Probe


RUN = 'bx-01-event-retention-01'
COMMON = """
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment, current_scope
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core import events
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_example_notes_labels.event_projection import HANDLER
from modular_platform import durable, event_store
from psycopg2.errors import SerializationFailure

assert env.cr.dbname == EXPECTED_DB and EXPECTED_DB.startswith('mp_disposable_r0_r1_release_')
actor = scoped_environment(api.Environment(env.cr, FIXTURE['users']['alice']['id'], {}),
                           FIXTURE['workspaces']['A']['public_id'])
scope = current_scope(actor)
release = current_release(env)
env.cr.execute('''SELECT b.public_id,i.id FROM mp_service_binding b
    JOIN mp_plugin_installation i ON i.id=b.consumer_id
    WHERE i.plugin_id='org.example.notes_labels' AND b.alias='documents'
        AND b.workspace_id=%s AND b.state='active' ''', [scope.workspace_id])
binding, installation = env.cr.fetchone()
site, digest = release['site_id'], release['release_digest']
topic = 'org.example.notes.changed'

def call(kind, **body):
    return events.dispatch(actor, dict(protocol=1, kind=kind+'_request', request_id=str(uuid4()), **body),
                           binding_id=binding)

def rejected(code, kind, **body):
    try:
        call(kind, **body)
    except PublicError as error:
        assert error.code == code, error.code
    else:
        raise AssertionError('Unexpected successful event request')
"""

SEED = """
note = actor['mp.example.note'].create({'title':'Disposable retention proof'})
key = str(uuid4())
old = call('subscribe', topic=topic, idempotency_key=key)
subscription = old['subscription_id']
assert old['replay_window_seconds'] == 604800
first = events.consume_registered(actor, subscription, HANDLER)
assert first['state'] == 'applied'
event = first['event_id']
assert call('replay', subscription_id=subscription, event_ids=[event])['replayed']
assert events.consume_registered(actor, subscription, HANDLER) == dict(state='duplicate', event_id=event)
summary = actor['mp.example.note.event.summary'].search([('note_id','=',note.public_id)])
assert len(summary) == 1 and summary.event_count == 1
env.cr.execute('''SELECT e.id,d.public_id,c.public_id FROM mp_outbox e
    JOIN mp_event_delivery d ON d.event_id=e.id JOIN mp_event_consumption c ON c.event_id=e.id
    WHERE e.public_id=%s AND d.state='acknowledged' ''', [event])
event_number, delivery, consumption = env.cr.fetchone()

note.with_context(expected_revision=1).write({'title':'Disposable retention proof updated'})
env.cr.execute('SELECT public_id FROM mp_outbox WHERE aggregate_id=%s AND aggregate_sequence=2',[note.public_id])
recent, = env.cr.fetchone()
active = call('subscribe', topic=topic, idempotency_key=str(uuid4()))['subscription_id']
held, grace = str(uuid4()), str(uuid4())
env.cr.execute('''INSERT INTO mp_outbox(public_id,site_id,workspace_id,actor_id,installation_id,plugin_id,topic,
        schema_version,aggregate_id,aggregate_sequence,occurred_at,correlation_id,causation_id,payload,
        release_digest,dispatch_generation,state)
    SELECT v.public_id,o.site_id,o.workspace_id,o.actor_id,o.installation_id,o.plugin_id,o.topic,
        o.schema_version,o.aggregate_id,o.aggregate_sequence,timezone('UTC',now())-v.age,o.correlation_id,
        o.causation_id,o.payload,o.release_digest,o.dispatch_generation,v.state
    FROM mp_outbox o CROSS JOIN (VALUES (%s,'held',interval '10 days'),(%s,'pending',interval '7 days 2 hours'))
        v(public_id,state,age) WHERE o.id=%s''', [held, grace, event_number])
env.cr.execute("UPDATE mp_outbox SET occurred_at=timezone('UTC',now())-interval '10 days' WHERE id=%s", [event_number])
env.cr.execute("UPDATE mp_event_subscription SET expires_at=timezone('UTC',now())-interval '9 days' WHERE public_id=%s", [subscription])
env.cr.execute('''UPDATE mp_event_delivery SET available_at=available_at-interval '10 days',
    lease_until=lease_until-interval '10 days',acknowledged_at=acknowledged_at-interval '10 days' WHERE public_id=%s''', [delivery])
env.cr.commit()
print('BX_EVENT='+json.dumps(dict(note=note.public_id, key=key, old_subscription=subscription,
    active=active, event=event, event_number=event_number, delivery=delivery, consumption=consumption,
    recent=recent, held=held, grace=grace)))
"""

AFTER = """
from modular_platform import event_retention
from modular_platform.dispatch_lifecycle import EVENT_HISTORY, LifecycleScope, observe

rejected('NOT_FOUND', 'replay', subscription_id=SEED['active'], event_ids=[SEED['event']])
rejected('NOT_FOUND', 'replay', subscription_id=SEED['active'], event_ids=[SEED['grace']])
rejected('CONFLICT', 'subscribe', topic=topic, idempotency_key=SEED['key'])
rejected('NOT_FOUND', 'status', subscription_id=SEED['old_subscription'])
assert not event_store.consume_once(env.cr, dict(workspace_id=scope.workspace_id, installation_id=installation,
    actor_id=scope.principal_id,site_id=site,release_digest=digest),
    dict(id=SEED['event_number'],public_id=SEED['event']), HANDLER)
summary = actor['mp.example.note.event.summary'].search([('note_id','=',SEED['note'])])
assert summary.event_count == 1
assert events.consume_registered(actor, SEED['active'], HANDLER) == dict(state='applied', event_id=SEED['recent'])
summary.invalidate_recordset(['event_count'])
assert summary.event_count == 2
env.cr.execute('SELECT public_id,state FROM mp_outbox WHERE public_id=ANY(%s)', [[SEED['event'],SEED['held'],SEED['grace']]])
assert dict(env.cr.fetchall()) == {SEED['held']:'held', SEED['grace']:'pending'}
env.cr.execute('SELECT kind,metadata,scope_key FROM mp_event_history ORDER BY kind')
rows={kind:(meta,key) for kind,meta,key in env.cr.fetchall()}
assert set(rows) == {'event','subscription','delivery','consumption'}
assert rows['consumption'][0]['event_id'] == SEED['event'] and rows['consumption'][1]
assert 'receipt' not in rows['delivery'][0] and 'payload' not in rows['event'][0] and rows['event'][0]['payload_digest']
assert 'idempotency_key' not in rows['subscription'][0] and rows['subscription'][1]
env.cr.commit()

# A pre-archive repeatable-read waiter may not recreate an expired key.
race_key = str(uuid4())
race_sub = call('subscribe',topic=topic,idempotency_key=race_key)['subscription_id']
env.cr.execute("UPDATE mp_event_subscription SET expires_at=timezone('UTC',now())-interval '9 days' WHERE public_id=%s",[race_sub])
env.cr.commit()
storage = durable.DispatchScope(site, scope.workspace_id, scope.principal_id, installation, digest)
with env.registry.cursor() as stale:
    stale.execute('SELECT count(*) FROM mp_event_history')
    stale.fetchone()
    with env.registry.cursor() as cleanup:
        cleanup.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        _, selected = event_retention.candidates(cleanup,site,digest,'subscription',datetime.now(timezone.utc)-timedelta(days=8),1,apply=True)
        assert [row[1] for row in selected] == [race_sub]
        event_retention.archive(cleanup,site,'subscription',selected)
        cleanup.commit()
    try:
        event_store.open_subscription(stale,storage,topic,{},race_key)
    except SerializationFailure:
        stale.rollback()
    else:
        raise AssertionError('Stale repeatable-read subscription escaped retention fence')
rejected('CONFLICT','subscribe',topic=topic,idempotency_key=race_key)

env.cr.execute('''INSERT INTO mp_event_history(site_id,workspace_id,kind,public_id,metadata,archived_at)
    SELECT %s,%s,'event',gen_random_uuid()::text,'{}'::jsonb,timezone('UTC',now()) FROM generate_series(1,100002)''',
    [site,scope.workspace_id])
retained = observe(env.cr,LifecycleScope(site,digest))['tables'][EVENT_HISTORY]
assert retained['rows'] == 100007
env.cr.rollback()
print('BX_EVENT='+json.dumps(dict(native_consumption_deduplicated=True,old_replay_refused=True,
    grace_period_preserved=True,held_preserved=True,new_consumer_effect_applied=True,
    expired_subscription_key_refused=True,stale_snapshot_refused=True,compact_rows_observed=retained['rows'])))
"""


def native(probe, label, program, *, seed=None):
    source = f"FIXTURE={probe.fixture!r}\nEXPECTED_DB={probe.state['database']!r}\nSEED={seed!r}\n" + COMMON + program
    raw = shell(probe, label, source)
    value, = [json.loads(line.split('=', 1)[1]) for line in raw.splitlines() if line.startswith('BX_EVENT=')]
    return value


def run():
    probe = Probe(RUN)
    seed_path = probe.site.local / 'event-retention-seed.json'
    if sys.argv[1:] == ['--resume-seed']:
        seed = load(seed_path)
        assert probe.sql('SELECT count(*) FROM mp_event_history') == '0'
    else:
        assert not seed_path.exists()
        seed = native(probe, 'bx01-event-seed', SEED)
        write(seed_path, seed)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()

    def review(kind):
        return probe.operator.run('archive-review', cutoff=cutoff, limit=1, kind=kind)

    assert review('event')['review']['records'] == []
    assert review('subscription')['review']['records'] == []
    for kind in ('delivery', 'consumption', 'event', 'subscription'):
        expected = seed[kind if kind != 'subscription' else 'old_subscription']
        reviewed = review(kind)
        assert reviewed['review']['records'] == [expected]
        approval = reviewed['approval']
        assert probe.operator.run('archive-status', approval=approval)['records'] == {expected:'live'}
        assert probe.operator.run('archive-apply', approval=approval)['records'] == [expected]
        assert probe.operator.run('archive-status', approval=approval)['records'] == {expected:'archived'}
    result = native(probe, 'bx01-event-after', AFTER, seed=seed)
    result.update(image=probe.state['image_id'], reviewed_kinds=['delivery','consumption','event','subscription'],
                  event_and_subscription_blocked_by_live_references=True)
    write(probe.site.local / 'event-retention-result.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    run()
