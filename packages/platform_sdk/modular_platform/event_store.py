"""Private bounded PostgreSQL receipt operations; caller supplies authority/tx.

These functions commit nothing, open no connection and grant no business access.
The native event adapter must authorize the current actor/binding/topic first.
"""
import hashlib
from uuid import uuid4
import rfc8785
from . import durable

RETENTION_SECONDS=604800
ACK_SECONDS=15
MAX_ATTEMPTS=5
MAX_REPLAYS=3


def open_subscription(cr,scope,topic,binding,key,origin=None):
    if not isinstance(scope,durable.DispatchScope):raise durable.QueueError('Typed subscription scope required')
    durable._uuid(key);durable._name(topic)
    if origin is not None:durable._uuid(origin)
    durable.control(cr,scope.site_id,scope.release_digest)
    digest=hashlib.sha256(rfc8785.dumps(dict(topic=topic,binding=binding,origin=origin))).hexdigest()
    cr.execute("""INSERT INTO mp_event_subscription(public_id,site_id,workspace_id,actor_id,installation_id,topic,binding,
        release_digest,origin_installation_id,idempotency_key,input_digest,state,created_at,expires_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,'active',timezone('UTC',clock_timestamp()),
        timezone('UTC',clock_timestamp())+interval '1 hour')
        ON CONFLICT(site_id,workspace_id,actor_id,installation_id,idempotency_key) DO NOTHING RETURNING public_id""",
        [str(uuid4()),scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id,topic,rfc8785.dumps(binding).decode(),scope.release_digest,origin,key,digest])
    fresh=cr.fetchone()
    if fresh:return lock_subscription(cr,fresh[0],scope)
    cr.execute("""SELECT public_id,input_digest,release_digest FROM mp_event_subscription
        WHERE site_id=%s AND workspace_id=%s AND actor_id=%s AND installation_id=%s AND idempotency_key=%s""",
        [scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id,key])
    old=cr.fetchone()
    if not old or tuple(old[1:])!=(digest,scope.release_digest):raise durable.QueueError('Subscription input/binding/release conflict')
    return lock_subscription(cr,old[0],scope,active=True)


def lock_subscription(cr,ident,scope,*,active=False):
    durable._uuid(ident)
    cr.execute("""SELECT to_jsonb(s),s.expires_at>timezone('UTC',clock_timestamp()) FROM mp_event_subscription s
        WHERE s.public_id=%s AND s.site_id=%s AND s.workspace_id=%s AND s.actor_id=%s AND s.installation_id=%s FOR UPDATE""",
        [ident,scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id])
    row=cr.fetchone()
    if not row:return None
    result=row[0];result['expired']=not row[1]
    if active and (result['state']!='active' or result['expired']):raise durable.QueueError('Subscription inactive or expired')
    return result


def require_dispatch(cr,subscription):
    durable.control(cr,subscription['site_id'],subscription['release_digest'])


def expire_leases(cr,subscription):
    require_dispatch(cr,subscription)
    cr.execute("""UPDATE mp_event_delivery SET state=CASE WHEN attempts>=5 THEN 'dead_letter' ELSE 'pending' END,
        receipt=NULL,lease_until=NULL,error_code='ACK_EXPIRED',available_at=timezone('UTC',clock_timestamp())+
        (LEAST(60,power(2,GREATEST(0,attempts-1))) * interval '1 second')
        WHERE subscription_id=%s AND state='leased' AND lease_until<=timezone('UTC',clock_timestamp())""",[subscription['id']])


def candidates(cr,subscription,limit):
    durable._bounded(limit,1,51)
    # Receipt anti-join, never an allocation-ID cursor. An uncommitted producer
    # is invisible now but remains eligible after it commits, even at a lower ID.
    cr.execute("""SELECT to_jsonb(o) FROM mp_outbox o LEFT JOIN mp_event_delivery d
        ON d.event_id=o.id AND d.subscription_id=%s
        WHERE o.site_id=%s AND o.workspace_id=%s AND o.topic=%s AND o.release_digest=%s
        AND o.state IN ('pending','published')
        AND o.occurred_at>=timezone('UTC',clock_timestamp())-interval '7 days'
        AND (d.id IS NULL OR d.state='pending' AND d.available_at<=timezone('UTC',clock_timestamp()))
        ORDER BY o.occurred_at,o.id LIMIT %s""",
        [subscription['id'],subscription['site_id'],subscription['workspace_id'],subscription['topic'],subscription['release_digest'],limit])
    return [row[0] for row in cr.fetchall()]


def lease(cr,subscription,event):
    require_dispatch(cr,subscription)
    cr.execute("""INSERT INTO mp_event_delivery(public_id,subscription_id,event_id,state,generation,attempts,replays,available_at)
        VALUES(%s,%s,%s,'pending',0,0,0,timezone('UTC',clock_timestamp()))
        ON CONFLICT(subscription_id,event_id) DO NOTHING""",[str(uuid4()),subscription['id'],event['id']])
    cr.execute("""UPDATE mp_event_delivery SET state='leased',generation=generation+1,attempts=attempts+1,
        receipt=%s,lease_until=LEAST(timezone('UTC',clock_timestamp())+interval '15 seconds',%s::timestamp,
        %s::timestamp+interval '7 days'),error_code=NULL
        WHERE subscription_id=%s AND event_id=%s AND state='pending' AND attempts<5
        AND available_at<=timezone('UTC',clock_timestamp()) RETURNING to_jsonb(mp_event_delivery)""",
        [str(uuid4()),subscription['expires_at'],event['occurred_at'],subscription['id'],event['id']])
    row=cr.fetchone()
    if not row:raise durable.QueueError('Delivery unavailable')
    cr.execute("UPDATE mp_outbox SET state='published' WHERE id=%s AND state='pending'",[event['id']])
    return row[0]


def lock_delivery(cr,subscription,receipt):
    durable._uuid(receipt['delivery_id']);durable._uuid(receipt['receipt']);durable._bounded(receipt['generation'],1,9007199254740991)
    cr.execute("""SELECT to_jsonb(d),d.lease_until>timezone('UTC',clock_timestamp()) FROM mp_event_delivery d
        WHERE d.public_id=%s AND d.subscription_id=%s FOR UPDATE""",[receipt['delivery_id'],subscription['id']])
    row=cr.fetchone()
    if not row or (row[0]['receipt'],row[0]['generation'])!=(receipt['receipt'],receipt['generation']):raise durable.QueueError('Obsolete event receipt')
    record=row[0]
    if record['state']=='acknowledged':return record
    if record['state']!='leased' or not row[1]:raise durable.QueueError('Event acknowledgement lease expired')
    return record


def acknowledge(cr,subscription,receipt):
    require_dispatch(cr,subscription);record=lock_delivery(cr,subscription,receipt)
    if record['state']=='acknowledged':return record['public_id']
    cr.execute("""UPDATE mp_event_delivery SET state='acknowledged',acknowledged_at=timezone('UTC',clock_timestamp())
        WHERE id=%s AND state='leased' AND receipt=%s AND generation=%s AND lease_until>timezone('UTC',clock_timestamp())
        RETURNING public_id""",[record['id'],receipt['receipt'],receipt['generation']])
    row=cr.fetchone()
    if not row:raise durable.QueueError('Event lease expired during consumer application')
    return row[0]


def delivery_status(cr,subscription):
    cr.execute("SELECT to_jsonb(d) FROM mp_event_delivery d WHERE subscription_id=%s ORDER BY (state='dead_letter') DESC,id LIMIT 51",[subscription['id']])
    return [row[0] for row in cr.fetchall()]


def dead_letter_count(cr,subscription):
    cr.execute("SELECT count(*) FROM mp_event_delivery WHERE subscription_id=%s AND state='dead_letter'",[subscription['id']]);return cr.fetchone()[0]


def replay(cr,subscription,events):
    require_dispatch(cr,subscription);ids=[]
    for event in events:
        cr.execute("""INSERT INTO mp_event_delivery(public_id,subscription_id,event_id,state,generation,attempts,replays,available_at)
            VALUES(%s,%s,%s,'pending',0,0,0,timezone('UTC',clock_timestamp())) ON CONFLICT(subscription_id,event_id) DO NOTHING""",
            [str(uuid4()),subscription['id'],event['id']])
        cr.execute("""UPDATE mp_event_delivery SET state='pending',generation=generation+1,attempts=0,replays=replays+1,
            receipt=NULL,lease_until=NULL,acknowledged_at=NULL,error_code=NULL,available_at=timezone('UTC',clock_timestamp())
            WHERE subscription_id=%s AND event_id=%s AND replays<3 RETURNING public_id""",[subscription['id'],event['id']])
        row=cr.fetchone()
        if not row:raise durable.QueueError('Event replay budget exhausted')
        ids.append(row[0])
    return ids


def consume_once(cr,subscription,event,handler):
    durable._name(handler)
    cr.execute("""INSERT INTO mp_event_consumption(public_id,workspace_id,actor_id,installation_id,event_id,handler,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,timezone('UTC',clock_timestamp()))
        ON CONFLICT(installation_id,workspace_id,handler,event_id) DO NOTHING RETURNING public_id""",
        [str(uuid4()),subscription['workspace_id'],subscription['actor_id'],subscription['installation_id'],event['id'],handler])
    return bool(cr.fetchone())


def lock_consumer(cr,subscription,handler):
    # A real MVCC update makes a waiting repeatable-read caller retry its full
    # native transaction with a fresh snapshot. This is control metadata, not a
    # raw-SQL replacement of the native business projection.
    cr.execute("""INSERT INTO mp_event_consumer_state(workspace_id,installation_id,handler,generation)
        VALUES(%s,%s,%s,1) ON CONFLICT(installation_id,workspace_id,handler)
        DO UPDATE SET generation=mp_event_consumer_state.generation+1 RETURNING id""",
        [subscription['workspace_id'],subscription['installation_id'],handler])
    return cr.fetchone()[0]


def consumer_failed(cr,subscription,receipt):
    record=lock_delivery(cr,subscription,receipt)
    cr.execute("""UPDATE mp_event_delivery SET state=CASE WHEN attempts>=5 THEN 'dead_letter' ELSE 'pending' END,
        receipt=NULL,lease_until=NULL,error_code='CONSUMER_FAILED',available_at=timezone('UTC',clock_timestamp())+
        (LEAST(60,power(2,GREATEST(0,attempts-1))) * interval '1 second') WHERE id=%s AND state='leased'""",[record['id']])


def close(cr,subscription):
    cr.execute("UPDATE mp_event_subscription SET state='closed' WHERE id=%s",[subscription['id']])
