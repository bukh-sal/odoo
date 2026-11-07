"""Verify the BX-01 history diagnostic on disposable PostgreSQL."""

import json
import os
from uuid import uuid4

import psycopg2
from psycopg2 import sql

from modular_platform.dispatch_lifecycle import (
    BASE,
    MAX_ROWS,
    SCHEMA,
    UNIQUE,
    DispatchLifecycleError,
    LifecycleScope,
    history_pressure,
    observe,
)


def run(connection):
    site = str(uuid4())
    release = 'sha256:' + '1' * 64
    scope = LifecycleScope(site, release)
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE ir_config_parameter (key varchar, value varchar)')
        cursor.execute(
            "INSERT INTO ir_config_parameter VALUES ('mp.site_id', %s), ('mp.release_digest', %s)",
            (site, release),
        )
        for table in sorted(BASE):
            columns = [
                sql.SQL('{} {}').format(sql.Identifier(name), sql.SQL(kind))
                for name, kind in SCHEMA[table].items()
            ]
            constraints = [
                sql.SQL('UNIQUE ({})').format(sql.SQL(', ').join(map(sql.Identifier, keys)))
                for keys in sorted(UNIQUE[table])
            ]
            cursor.execute(
                sql.SQL('CREATE TABLE {} ({})').format(
                    sql.Identifier(table), sql.SQL(', ').join(columns + constraints)
                )
            )
        cursor.execute(
            "INSERT INTO mp_dispatch_control (site_id, release_digest, state, generation) "
            "VALUES (%s, %s, 'paused', 1)", (site, release),
        )
        cursor.execute(
            "INSERT INTO mp_job (id, site_id, state) "
            "SELECT n, %s, 'completed' FROM generate_series(1, %s) n",
            (site, MAX_ROWS * 4 // 5),
        )
        assert history_pressure(cursor, scope)['tables']['mp_job'] == {
            'rows_observed': 80_000, 'count_is_lower_bound': False,
            'rows_until_limit': 20_000, 'status': 'approaching_limit',
        }
        cursor.execute(
            "INSERT INTO mp_job (id, site_id, state) "
            "SELECT n, %s, 'completed' FROM generate_series(80001, %s) n",
            (site, MAX_ROWS),
        )
        assert history_pressure(cursor, scope)['tables']['mp_job']['status'] == 'at_limit'
        cursor.execute(
            "INSERT INTO mp_job (id, site_id, state) VALUES (100001, %s, 'completed'), "
            "(100002, %s, 'completed')", (site, site),
        )
        try:
            observe(cursor, scope)
        except DispatchLifecycleError as exc:
            assert 'row bound exceeded' in str(exc)
        else:
            raise AssertionError('Oversized lifecycle snapshot should be refused')
        result = history_pressure(cursor, scope)
        assert result['tables']['mp_job'] == {
            'rows_observed': MAX_ROWS + 1, 'count_is_lower_bound': True,
            'rows_until_limit': 0, 'status': 'over_limit',
        }
        assert result['tables']['mp_outbox']['status'] == 'below_warning'
        try:
            history_pressure(cursor, LifecycleScope(str(uuid4()), release))
        except DispatchLifecycleError as exc:
            assert 'site or published release changed' in str(exc)
        else:
            raise AssertionError('Foreign scope should be refused')
    connection.rollback()
    return result


if __name__ == '__main__':
    database = os.environ['MP_BX_FIXTURE_DATABASE']
    if database != 'mp_bx_history_probe':
        raise SystemExit('Exact disposable BX fixture database required')
    with psycopg2.connect(host='127.0.0.1', dbname=database, user='postgres', connect_timeout=5) as conn:
        print(json.dumps(run(conn), sort_keys=True))
