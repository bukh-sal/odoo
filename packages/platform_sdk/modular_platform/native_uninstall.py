"""Fixed approved maintenance child; real upstream uninstall, never HTTP.

Invoked only after the existing independent executor reserves approval, drains
workers and checkpoints. Native commits/uncertain outcomes require recovery.
"""
import configparser
import hashlib
import json
from pathlib import Path
import sys


def snapshot_relations(connection, impact):
    """Observe aggregates/schema only; static relation names are quoted data."""
    from psycopg2 import sql
    relations = sorted({row['relation'] for row in impact['models'] + impact['fields'] if row['relation'] is not None})
    result = {}
    with connection.cursor() as cursor:
        for table in relations:
            cursor.execute("SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                           "WHERE n.nspname='public' AND c.relname=%s AND c.relkind IN ('r','p')", [table])
            row = cursor.fetchone()
            if row is None:
                result[table] = None
                continue
            oid = row[0]
            cursor.execute('SELECT attname,format_type(atttypid,atttypmod),attnotnull FROM pg_attribute '
                           'WHERE attrelid=%s AND attnum>0 AND NOT attisdropped ORDER BY attnum', [oid])
            columns = [dict(name=name, type=type_name, required=required) for name, type_name, required in cursor.fetchall()]
            cursor.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)))
            records = cursor.fetchone()[0]
            cursor.execute('SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s ORDER BY conname', [oid])
            constraints = [dict(name=name, definition=definition) for name, definition in cursor.fetchall()]
            result[table] = dict(columns=columns, records=records, constraints=constraints)
    return result


def require_exact_native_closure(approved, actual):
    if not approved or len(set(approved)) != len(approved) or set(approved) != set(actual):
        raise ValueError('Actual upstream native dependent closure differs from the approved module set')


def main():
    import psycopg2
    from modular_platform.lifecycle_impact import impact_view, inspect_native_impact
    from modular_platform.plans import data_digest

    data = json.load(sys.stdin)
    assert set(data) == {'database', 'site_id', 'deployment_id', 'operation_id', 'plan_hash',
                         'impact', 'plugins', 'inventory_digest'}
    impact_view(data['impact'], operation_id=data['operation_id'], plan_hash=data['plan_hash'], observed_at='2026-10-29T00:00:00Z')
    assert data['impact']['site_id'] == data['site_id'] and data['impact']['dispatch']['state'] == 'not_present'
    config = configparser.ConfigParser(); config.read('/run/secrets/odoo_config'); options = config['options']
    assert options['db_name'] == data['database'], 'Controlled maintenance target mismatch'
    root = Path('/opt/modular')
    raw_inventory = (root / 'distribution-inventory.json').read_bytes()
    assert 'sha256:' + hashlib.sha256(raw_inventory).hexdigest() == data['inventory_digest'], 'Controlled image inventory mismatch'
    inventory = json.loads(raw_inventory)
    descriptors = list(data['plugins'].values())
    addons = {'mp_identity'} | {d['manifest']['runtime']['addon_name'] for d in descriptors}
    sources = {}
    for name, digest in inventory['files'].items():
        if name.startswith('addons/') and name.endswith('.py') and name.split('/')[1] in addons:
            raw = (root / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest, 'Controlled native source drift'
            sources[name[len('addons/'):]] = raw
    for descriptor in descriptors:
        addon = descriptor['manifest']['runtime']['addon_name']; prefix = 'backend/odoo_addons/' + addon + '/'
        for name, digest in descriptor['inventory'].items():
            if name.startswith(prefix) and name.endswith('.py'):
                assert hashlib.sha256(sources[addon + '/' + name[len(prefix):]]).hexdigest() == digest

    def connect():
        connection = psycopg2.connect(host=options['db_host'], port=options.getint('db_port'), user=options['db_user'],
            password=options['db_password'], dbname=data['database'], connect_timeout=10)
        connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
        return connection

    connection = connect()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='5s'")
            cursor.execute("SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id'")
            assert cursor.fetchone() == (data['deployment_id'],)
            cursor.execute("SELECT name,latest_version FROM ir_module_module WHERE state='installed' ORDER BY name")
            native_before = dict(cursor.fetchall())
        current = inspect_native_impact(connection, site_id=data['site_id'], requested=data['impact']['requested_addons'],
                                        descriptors=descriptors, sources=sources)
        assert current == data['impact'], 'Uninstall counts/schema/ownership changed after approval'
        before = snapshot_relations(connection, current)
    connection.close()
    print(json.dumps(dict(kind='native_uninstall_before', operation_id=data['operation_id'], plan_hash=data['plan_hash'],
                          impact_digest=data_digest(current), relations=before, native_versions=native_before)), flush=True)

    # No registry or native hooks are loaded until after exact impact validation
    # in the executor's recorded mutation phase with a verified checkpoint.
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.modules.registry import Registry
    odoo.tools.config.parse_config(['-c', '/run/secrets/odoo_config', '-d', data['database'],
        '--no-http', '--workers=0', '--max-cron-threads=0', '--without-demo'])
    registry = Registry.new(data['database'])
    approved = data['impact']['native_closure']
    with registry.cursor() as cursor:
        env = api.Environment(cursor, SUPERUSER_ID, {})
        modules = env['ir.module.module'].search([('name', 'in', approved)])
        assert len(modules) == len(approved) and all(m.state == 'installed' for m in modules)
        actual = set(modules.mapped('name')) | set(modules.downstream_dependencies().mapped('name'))
        require_exact_native_closure(approved, actual)
        modules.button_immediate_uninstall()
        cursor.commit()

    connection = connect()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='5s'")
            cursor.execute('SELECT name,state,latest_version FROM ir_module_module WHERE name=ANY(%s) ORDER BY name', [approved])
            removed = [dict(addon=name, state=state, version=version) for name, state, version in cursor.fetchall()]
            assert len(removed) == len(approved) and all(m['state'] == 'uninstalled' for m in removed)
            cursor.execute("SELECT name,latest_version FROM ir_module_module WHERE state='installed' ORDER BY name")
            assert dict(cursor.fetchall()) == {k: v for k, v in native_before.items() if k not in approved}, 'Surviving native modules changed unexpectedly'
            cursor.execute('SELECT module,model,count(*) FROM ir_model_data WHERE module=ANY(%s) GROUP BY module,model ORDER BY module,model', [approved])
            remaining_metadata = [dict(native_addon=addon, model=model, records=count) for addon, model, count in cursor.fetchall()]
        after = snapshot_relations(connection, current)
    connection.close()
    print(json.dumps(dict(kind='native_uninstall_effects', operation_id=data['operation_id'], plan_hash=data['plan_hash'],
        impact_digest=data_digest(current), before=before, after=after, native_after=removed,
        remaining_owned_metadata=remaining_metadata, surviving_native_versions_unchanged=True,
        source_artifacts_retained=True, arbitrary_hooks_fully_trusted=True)), flush=True)


if __name__ == '__main__': main()
