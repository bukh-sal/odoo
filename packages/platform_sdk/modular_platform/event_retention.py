"""Bounded archive for expired events and their private routing receipts."""

from . import durable
from .plans import data_digest


POLICY = 'native-event-v1'
MINIMUM_DAYS = 8
MAX_BATCH = 25

_SELECT = {
    'delivery': """SELECT r.id,r.public_id,s.workspace_id,jsonb_build_object(
            'event_id',o.public_id,'subscription_id',s.public_id,'state',r.state,
            'attempts',r.attempts,'replays',r.replays,'acknowledged_at',r.acknowledged_at)
        FROM mp_event_delivery r JOIN mp_event_subscription s ON s.id=r.subscription_id
        JOIN mp_outbox o ON o.id=r.event_id
        WHERE o.site_id=%(site)s AND s.site_id=o.site_id AND s.workspace_id=o.workspace_id AND s.topic=o.topic
          AND o.state IN ('pending','published') AND o.occurred_at<=%(cutoff)s
          AND s.expires_at<=%(cutoff)s + interval '7 days 1 hour'
          AND (r.lease_until IS NULL OR r.lease_until<=%(cutoff)s + interval '7 days 1 hour')""",
    'consumption': """SELECT r.id,r.public_id,r.workspace_id,jsonb_build_object(
            'event_id',o.public_id,'actor_id',r.actor_id,'installation_id',r.installation_id,
            'handler',r.handler,'created_at',r.created_at)
        FROM mp_event_consumption r JOIN mp_outbox o ON o.id=r.event_id
        WHERE o.site_id=%(site)s AND r.workspace_id=o.workspace_id
          AND o.state IN ('pending','published') AND o.occurred_at<=%(cutoff)s""",
    'event': """SELECT r.id,r.public_id,r.workspace_id,jsonb_build_object(
            'topic',r.topic,'occurred_at',r.occurred_at,'state',r.state,
            'payload_digest','sha256:'||encode(sha256(convert_to(r.payload::text,'UTF8')),'hex'))
        FROM mp_outbox r WHERE r.site_id=%(site)s AND r.state IN ('pending','published') AND r.occurred_at<=%(cutoff)s
          AND NOT EXISTS (SELECT 1 FROM mp_event_delivery d WHERE d.event_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM mp_event_consumption c WHERE c.event_id=r.id)""",
    'subscription': """SELECT r.id,r.public_id,r.workspace_id,jsonb_build_object(
            'actor_id',r.actor_id,'installation_id',r.installation_id,'topic',r.topic,
            'release_digest',r.release_digest,'input_digest',r.input_digest,
            'state',r.state,'expires_at',r.expires_at,'idempotency_key',r.idempotency_key)
        FROM mp_event_subscription r WHERE r.site_id=%(site)s AND r.state IN ('active','closed') AND r.expires_at<=%(cutoff)s
          AND NOT EXISTS (SELECT 1 FROM mp_event_delivery d WHERE d.subscription_id=r.id)""",
}
TABLES = dict(event='mp_outbox', delivery='mp_event_delivery', consumption='mp_event_consumption',
              subscription='mp_event_subscription')


def subscription_key(workspace, actor, installation, key):
    return data_digest([workspace, actor, installation, key])


def consumption_key(workspace, installation, handler, event):
    return data_digest([workspace, installation, handler, event])


def retained(cr, site, kind, key):
    cr.execute('SELECT 1 FROM mp_event_history WHERE site_id=%s AND kind=%s AND scope_key=%s', [site, kind, key])
    return bool(cr.fetchone())


def candidates(cr, site, release, kind, cutoff, limit, *, apply=False):
    durable._uuid(site)
    durable._bounded(limit, 1, MAX_BATCH)
    if kind not in TABLES:
        raise durable.QueueError('Known event retention record kind required')
    utc = durable._archive_cutoff(cutoff)
    if apply:
        cr.execute('SHOW transaction_isolation')
        if cr.fetchone() != ('read committed',):
            raise durable.QueueError('Event archive apply requires fresh read-committed selection')
        # Event writers take a shared dispatch lock. Write a new MVCC version
        # without changing the generation so a stale waiter must restart.
        cr.execute("""UPDATE mp_dispatch_control SET generation=generation
            WHERE site_id=%s AND release_digest=%s AND state='enabled' RETURNING generation""", [site, release])
        row = cr.fetchone()
        if not row:
            raise durable.DispatchPaused('Event archive requires current enabled dispatch')
        generation = row[0]
    else:
        generation = durable.control(cr, site, release)
    cr.execute("""SELECT %s<=timezone('UTC',statement_timestamp())-(%s*interval '1 day'),
        EXISTS(SELECT 1 FROM mp_plugin_installation WHERE runtime<>'native')
        OR EXISTS(SELECT 1 FROM mp_service_credential WHERE state='active')
        OR EXISTS(SELECT 1 FROM res_users_apikeys)""", [utc, MINIMUM_DAYS])
    cutoff_safe, external = cr.fetchone()
    if not cutoff_safe or external:
        raise durable.QueueError('Event archive requires its minimum retention window and a native-only profile')
    query = _SELECT[kind] + ' ORDER BY r.id LIMIT %(limit)s'
    cr.execute(query, dict(site=site, cutoff=utc, limit=limit))
    return generation, cr.fetchall()


def archive(cr, site, kind, rows):
    """Move the exact reviewed rows under the exclusive dispatch lock."""
    for row_id, public_id, workspace, metadata in rows:
        metadata = dict(metadata)
        key = None
        if kind == 'subscription':
            key = subscription_key(workspace, metadata['actor_id'], metadata['installation_id'], metadata.pop('idempotency_key'))
        elif kind == 'consumption':
            key = consumption_key(workspace, metadata['installation_id'], metadata['handler'], metadata['event_id'])
        cr.execute("""INSERT INTO mp_event_history(site_id,workspace_id,kind,public_id,scope_key,metadata,archived_at)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,timezone('UTC',statement_timestamp()))""",
            [site, workspace, kind, public_id, key, durable._json(metadata)[0]])
        cr.execute('DELETE FROM ' + TABLES[kind] + ' WHERE id=%s AND public_id=%s RETURNING id', [row_id, public_id])
        if cr.fetchone() != (row_id,):
            raise durable.QueueError('Reviewed event archive record changed')


def status(cr, site, kind, ids):
    if kind not in TABLES or not isinstance(ids, list) or not 1 <= len(ids) <= MAX_BATCH:
        raise durable.QueueError('Explicit bounded event archive IDs required')
    for ident in ids:
        durable._uuid(ident)
    if len(set(ids)) != len(ids):
        raise durable.QueueError('Event archive IDs must be distinct')
    source = TABLES[kind] + ' r'
    owner = 'r.site_id'
    if kind in {'delivery', 'consumption'}:
        source += ' JOIN mp_outbox o ON o.id=r.event_id'
        owner = 'o.site_id'
    cr.execute(f"""SELECT wanted.id, CASE
            WHEN live.public_id IS NOT NULL AND a.id IS NOT NULL THEN 'conflict'
            WHEN live.public_id IS NOT NULL THEN 'live' WHEN a.id IS NOT NULL THEN 'archived' ELSE 'missing' END
        FROM unnest(%s::text[]) AS wanted(id)
        LEFT JOIN (SELECT r.public_id FROM {source} WHERE {owner}=%s AND r.public_id=ANY(%s)) live ON live.public_id=wanted.id
        LEFT JOIN mp_event_history a ON a.site_id=%s AND a.kind=%s AND a.public_id=wanted.id""", [ids, site, ids, site, kind])
    return dict(cr.fetchall())
