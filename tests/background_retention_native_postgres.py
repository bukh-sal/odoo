"""Exercise the real BX-01 enqueue and archive SQL in disposable PostgreSQL."""

from datetime import datetime, timedelta, timezone
import json
import os
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.errors import SerializationFailure

from background_postgres import DDL, expect
from modular_platform import durable
from modular_platform.dispatch_lifecycle import (
    JOB_IDENTITY,
    PHYSICAL_SCHEMA,
    UNIQUE,
    _identity_snapshot,
)


def run(archiver, producer):
    site = str(uuid4())
    release = 'sha256:' + '1' * 64
    scope = durable.DispatchScope(site, 1, 2, 3, release)
    handler = 'org.example.bx:retention'
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)

    def enqueue(cursor, key, value=1, **options):
        return durable.enqueue(
            cursor, scope, handler, 1, {'value': value}, key,
            retain_identity=options.pop('retain_identity', True), **options,
        )

    def archive(cursor, limit=1):
        return durable.archive_terminal_jobs(cursor, site, release, cutoff=cutoff, limit=limit)

    def finish(cursor, job_id, state='completed'):
        cursor.execute("""UPDATE mp_job SET state=%s,deadline_at=%s,finished_at=%s
            WHERE public_id=%s""", [state, cutoff, cutoff, job_id])

    with archiver.cursor() as cr:
        cr.execute(DDL.replace('CREATE TEMP TABLE', 'CREATE TABLE'))
        columns = [
            sql.SQL('{} {}').format(sql.Identifier(name), sql.SQL('serial' if name == 'id' else kind))
            for name, kind in PHYSICAL_SCHEMA[JOB_IDENTITY].items()
        ]
        columns += [
            sql.SQL('UNIQUE ({})').format(sql.SQL(', ').join(map(sql.Identifier, keys)))
            for keys in sorted(UNIQUE[JOB_IDENTITY])
        ]
        cr.execute(sql.SQL('CREATE TABLE {} ({})').format(
            sql.Identifier(JOB_IDENTITY), sql.SQL(', ').join(columns)))
        durable.set_control(cr, site, release, 'enabled')
        # Old rows from a retained image had no shared identity record.
        original = enqueue(cr, 'legacy-row', retain_identity=False)
        finish(cr, original)
        held = enqueue(cr, 'held')
        finish(cr, held, 'held')
        remote = enqueue(cr, 'remote', effect_mode='reconcile')
        finish(cr, remote)
        waiting = enqueue(cr, 'waiting')
    archiver.commit()
    producer.set_session(isolation_level='REPEATABLE READ')

    with producer.cursor() as producer_cr, archiver.cursor() as archive_cr:
        producer_cr.execute('SELECT count(*) FROM mp_job')  # Establish the old snapshot.
        assert archive(archive_cr) == [original]
        archiver.commit()
        expect(SerializationFailure, enqueue, producer_cr, 'legacy-row')
        producer.rollback()
        assert enqueue(producer_cr, 'legacy-row', on_new=lambda: 1 / 0) == original
        expect(durable.QueueError, enqueue, producer_cr, 'legacy-row', value=2)
        producer.rollback()

        rollback_job = enqueue(archive_cr, 'rollback')
        finish(archive_cr, rollback_job)
        archiver.commit()
        assert archive(archive_cr) == [rollback_job]
        archiver.rollback()
        assert enqueue(producer_cr, 'rollback') == rollback_job
        producer.commit()

        archiver.set_session(isolation_level='REPEATABLE READ')
        archive_cr.execute('SELECT count(*) FROM mp_job')  # Archiver now starts first.
        assert enqueue(producer_cr, 'rollback') == rollback_job
        producer.commit()
        expect(SerializationFailure, archive, archive_cr)
        archiver.rollback()
        assert archive(archive_cr) == [rollback_job]
        archiver.commit()
        assert archive(archive_cr, limit=2) == []
        archive_cr.execute('SELECT public_id FROM mp_job ORDER BY public_id')
        assert sorted(row[0] for row in archive_cr.fetchall()) == sorted((held, remote, waiting))
        archive_cr.execute("""INSERT INTO mp_job_identity (site_id,idempotency_key)
            SELECT %s,'history:'||n FROM generate_series(1,100002) n""", [site])
        receipt = _identity_snapshot(archive_cr, site)
        assert receipt['rows'] == 100007
        assert _identity_snapshot(archive_cr, site) == receipt
        archive_cr.execute("UPDATE mp_job_identity SET terminal_state='cancelled' WHERE job_public_id=%s", [original])
        assert _identity_snapshot(archive_cr, site)['sha256'] != receipt['sha256']
        archiver.rollback()
    return {
        'legacy_row_archived': True,
        'both_stale_transaction_orders_refused': True,
        'duplicate_returned_original_without_preflight': True,
        'changed_input_refused': True,
        'archive_rollback_preserved_job': True,
        'held_remote_and_waiting_jobs_preserved': True,
        'identity_snapshot_rows': receipt['rows'],
        'identity_digest_detected_change': True,
    }


if __name__ == '__main__':
    database = os.environ['MP_BX_FIXTURE_DATABASE']
    if database != 'mp_bx_native_retention':
        raise SystemExit('Exact disposable BX fixture database required')
    settings = dict(host='127.0.0.1', dbname=database, user='postgres', connect_timeout=5)
    with psycopg2.connect(**settings) as archiver, psycopg2.connect(**settings) as enqueuer:
        print(json.dumps(run(archiver, enqueuer), sort_keys=True))
