"""Fixed maintenance child: publish exact approved native install metadata.

Executed by the OS executor in a stopped, isolated deployment, never by HTTP.
Input is data, with no Python/template/SQL supplied by a plan.
"""
import configparser
import json
import sys

import psycopg2
from psycopg2.extras import Json


def main():
    data = json.load(sys.stdin)
    assert set(data) == {'site_id', 'deployment_id', 'operation_id', 'generation', 'release_digest', 'targets', 'plugins', 'bindings'}
    config = configparser.ConfigParser()
    config.read('/run/secrets/odoo_config')
    options = config['options']
    connection = psycopg2.connect(host=options['db_host'], port=options.getint('db_port'), user=options['db_user'],
        password=options['db_password'], dbname=options['db_name'], connect_timeout=10)
    with connection:
        with connection.cursor() as cursor:
            for key, expected in [('mp.site_id', data['site_id']), ('mp.deployment_id', data['deployment_id'])]:
                cursor.execute('SELECT value FROM ir_config_parameter WHERE key=%s', [key])
                assert cursor.fetchone() == (expected,), 'Maintenance target identity mismatch'
            installations, workspaces = {}, {}
            for target in data['targets']:
                assert target['action'] == 'install' and target['site_id'] == data['site_id']
                plugin = data['plugins'][target['plugin_id']]
                manifest = plugin['manifest']
                cursor.execute('SELECT state,latest_version FROM ir_module_module WHERE name=%s', [manifest['runtime']['addon_name']])
                assert cursor.fetchone() == ('installed', '19.0.' + manifest['plugin']['version']), 'Native installed version differs'
                cursor.execute('SELECT id,state FROM mp_workspace WHERE public_id=%s FOR UPDATE', [target['workspace_id']])
                row = cursor.fetchone()
                assert row and row[1] == 'active', 'Workspace is unavailable'
                workspace = row[0]
                workspaces[target['workspace_id']] = workspace
                cursor.execute('SELECT id,public_id,version,artifact_digest,state FROM mp_plugin_installation WHERE plugin_id=%s FOR UPDATE', [target['plugin_id']])
                row = cursor.fetchone()
                if row:
                    assert row[1:] == (target['installation_id'], manifest['plugin']['version'], plugin['digest'], 'installed'), 'Installation identity changed'
                    installation = row[0]
                else:
                    cursor.execute('''INSERT INTO mp_plugin_installation(public_id,plugin_id,version,artifact_digest,runtime,state,manifest,create_uid,write_uid,create_date,write_date)
                        VALUES (%s,%s,%s,%s,'native','installed',%s,1,1,timezone('UTC',now()),timezone('UTC',now())) RETURNING id''',
                        [target['installation_id'], target['plugin_id'], manifest['plugin']['version'], plugin['digest'], Json(manifest)])
                    installation = cursor.fetchone()[0]
                installations[target['installation_id']] = installation
                cursor.execute('''INSERT INTO mp_workspace_plugin(workspace_id,plugin_id,installation_id,availability,create_uid,write_uid,create_date,write_date)
                    VALUES (%s,%s,%s,'enabled',1,1,timezone('UTC',now()),timezone('UTC',now()))''', [workspace, target['plugin_id'], installation])
            # Existing bindings elsewhere are preserved; only missing or changed
            # exact descriptors are written, after checking immutable ownership.
            for binding in data['bindings']:
                assert binding['site_id'] == data['site_id']
                cursor.execute('SELECT id FROM mp_workspace WHERE public_id=%s', [binding['workspace_id']])
                workspace = cursor.fetchone()[0]
                cursor.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s', [binding['consumer_installation_id']])
                consumer = cursor.fetchone()[0]
                cursor.execute('SELECT id,public_id,workspace_id,consumer_id,alias,descriptor FROM mp_service_binding WHERE public_id=%s OR (workspace_id=%s AND consumer_id=%s AND alias=%s)',
                    [binding['binding_id'], workspace, consumer, binding['alias']])
                rows = cursor.fetchall()
                if rows:
                    assert len(rows) == 1 and rows[0][1:5] == (binding['binding_id'], workspace, consumer, binding['alias']), 'Binding identity changed'
                    assert rows[0][5] == binding, 'Install must preserve existing binding descriptors'
                else:
                    cursor.execute('''INSERT INTO mp_service_binding(public_id,workspace_id,consumer_id,alias,descriptor,state,create_uid,write_uid,create_date,write_date)
                        VALUES (%s,%s,%s,%s,%s,'active',1,1,timezone('UTC',now()),timezone('UTC',now()))''',
                        [binding['binding_id'], workspace, consumer, binding['alias'], Json(binding)])
            cursor.execute('UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=ANY(%s)', [list(workspaces.values())])
            for key, value in [('mp.release_generation', str(data['generation'])), ('mp.release_digest', data['release_digest']), ('mp.last_operation_id', data['operation_id'])]:
                cursor.execute('''INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date) VALUES (%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now()))
                    ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date''', [key, value])
    connection.close()
    print(json.dumps({'metadata_published': True, 'operation_id': data['operation_id']}))


if __name__ == '__main__':
    main()
