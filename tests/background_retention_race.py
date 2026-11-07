"""Probe the BX-01 archive race and candidate identity fence on PostgreSQL."""

import json
import os

import psycopg2
from psycopg2.errors import SerializationFailure


def statement(connection, query, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        if cursor.description:
            return cursor.fetchall()


def run(archive, producer):
    statement(archive, 'CREATE TABLE bx_live (key text PRIMARY KEY, public_id text)')
    statement(archive, 'CREATE TABLE bx_receipt (key text PRIMARY KEY, public_id text)')
    statement(archive, "INSERT INTO bx_live VALUES ('unsafe', 'original'), ('safe', 'original')")
    statement(archive, "INSERT INTO bx_receipt VALUES ('safe', NULL)")
    archive.commit()
    producer.set_session(isolation_level='REPEATABLE READ')

    # A split archive lookup and live unique index cannot protect an older
    # transaction after the archive move commits.
    assert statement(producer, "SELECT public_id FROM bx_receipt WHERE key='unsafe'") == []
    statement(archive, "INSERT INTO bx_receipt VALUES ('unsafe', 'original')")
    statement(archive, "DELETE FROM bx_live WHERE key='unsafe'")
    archive.commit()
    assert statement(producer, "SELECT public_id FROM bx_receipt WHERE key='unsafe'") == []
    statement(producer, "INSERT INTO bx_live VALUES ('unsafe', 'duplicate')")
    producer.commit()
    assert statement(archive, "SELECT public_id FROM bx_live WHERE key='unsafe'") == [('duplicate',)]
    archive.commit()

    # Both paths writing the same identity row forces PostgreSQL to reject
    # a stale snapshot. A fresh transaction reads the archived outcome.
    reserve = """
        INSERT INTO bx_receipt AS receipt VALUES (%s, NULL)
        ON CONFLICT (key) DO UPDATE SET public_id = receipt.public_id
        RETURNING public_id
    """
    assert statement(producer, "SELECT public_id FROM bx_receipt WHERE key='safe'") == [(None,)]
    assert statement(archive, reserve, ('safe',)) == [(None,)]
    statement(archive, "UPDATE bx_receipt SET public_id='original' WHERE key='safe'")
    statement(archive, "DELETE FROM bx_live WHERE key='safe'")
    archive.commit()
    try:
        statement(producer, reserve, ('safe',))
    except SerializationFailure as error:
        assert error.pgcode == '40001'
        producer.rollback()
    else:
        raise AssertionError('A stale transaction acquired a modified identity')
    assert statement(producer, reserve, ('safe',)) == [('original',)]
    assert statement(producer, "SELECT public_id FROM bx_live WHERE key='safe'") == []
    producer.commit()

    statement(archive, "INSERT INTO bx_live VALUES ('rollback', 'original')")
    archive.commit()
    assert statement(archive, reserve, ('rollback',)) == [(None,)]
    statement(archive, "UPDATE bx_receipt SET public_id='original' WHERE key='rollback'")
    statement(archive, "DELETE FROM bx_live WHERE key='rollback'")
    archive.rollback()
    assert statement(producer, reserve, ('rollback',)) == [(None,)]
    assert statement(producer, "SELECT public_id FROM bx_live WHERE key='rollback'") == [('original',)]
    producer.rollback()
    return {
        'split_lookup_created_duplicate': True,
        'shared_row_refused_stale_snapshot': '40001',
        'fresh_retry_observed_original': True,
        'rolled_back_move_preserved_live_row': True,
    }


if __name__ == '__main__':
    database = os.environ['MP_BX_FIXTURE_DATABASE']
    if database != 'mp_bx_retention_race':
        raise SystemExit('Exact disposable BX fixture database required')
    settings = dict(host='127.0.0.1', dbname=database, user='postgres', connect_timeout=5)
    with psycopg2.connect(**settings) as archiver, psycopg2.connect(**settings) as enqueuer:
        print(json.dumps(run(archiver, enqueuer), sort_keys=True))
