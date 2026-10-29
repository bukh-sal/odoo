"""Fixed post-native-uninstall publication; tombstones, no source deletion."""
import configparser
import hashlib
import json
from pathlib import Path
import sys


def main():
    import psycopg2
    data = json.load(sys.stdin)
    assert set(data) == {'site_id', 'deployment_id', 'operation_id', 'generation', 'release_digest', 'targets',
                         'plugins', 'bindings', 'permission_changes', 'previous_plugins', 'database', 'policy_version'}
    config = configparser.ConfigParser(); config.read('/run/secrets/odoo_config'); options = config['options']
    assert options['db_name'] == data['database']
    connection = psycopg2.connect(host=options['db_host'], port=options.getint('db_port'), user=options['db_user'],
        password=options['db_password'], dbname=data['database'], connect_timeout=10)
    with connection:
        with connection.cursor() as cursor:
            for key, value in [('mp.site_id', data['site_id']), ('mp.deployment_id', data['deployment_id'])]:
                cursor.execute('SELECT value FROM ir_config_parameter WHERE key=%s', [key])
                assert cursor.fetchone() == (value,), 'Post-uninstall target identity mismatch'
            cursor.execute("SELECT to_regclass('mp_job'),to_regclass('mp_outbox')")
            assert cursor.fetchone() == (None, None), 'Unsupported durable dispatch requires G6 reconciliation'
            assert data['targets'] and all(t['action'] == 'uninstall' and t['site_id'] == data['site_id'] for t in data['targets'])
            installation_ids, public_ids, workspaces, actual_revocations = [], [], set(), []
            for plugin_id in sorted({t['plugin_id'] for t in data['targets']}):
                descriptor = data['plugins'][plugin_id]; manifest = descriptor['manifest']
                assert manifest['runtime']['kind'] == 'native'
                cursor.execute('SELECT state FROM ir_module_module WHERE name=%s', [manifest['runtime']['addon_name']])
                assert cursor.fetchone() == ('uninstalled',), 'Native uninstall did not finish'
                cursor.execute('SELECT id,public_id,version,artifact_digest,state FROM mp_plugin_installation WHERE plugin_id=%s FOR UPDATE', [plugin_id])
                row = cursor.fetchone()
                assert row and row[2:] == (manifest['plugin']['version'], descriptor['digest'], 'installed'), 'Installation preimage changed'
                installation, public_id = row[:2]
                targets = [t for t in data['targets'] if t['plugin_id'] == plugin_id]
                assert all(t['installation_id'] == public_id for t in targets), 'Stable installation identity changed'
                cursor.execute('''SELECT w.public_id,w.id,f.plugin_id FROM mp_workspace_plugin f
                    JOIN mp_workspace w ON w.id=f.workspace_id WHERE f.installation_id=%s ORDER BY w.public_id''', [installation])
                scopes = cursor.fetchall()
                assert scopes and all(s[2] == plugin_id for s in scopes)
                assert sorted(t['workspace_id'] for t in targets) == [s[0] for s in scopes], 'Uninstall omitted a registered workspace'
                workspaces.update(s[1] for s in scopes)
                cursor.execute('''SELECT w.public_id,g.capability FROM mp_plugin_grant g JOIN mp_workspace w ON w.id=g.workspace_id
                    WHERE g.installation_id=%s AND g.state='approved' ORDER BY w.public_id,g.capability''', [installation])
                actual_revocations.extend(dict(plugin_id=plugin_id, workspace_id=workspace, capability=capability, action='revoke')
                                          for workspace, capability in cursor.fetchall())
                installation_ids.append(installation); public_ids.append(public_id)
            order = lambda r: (r['plugin_id'], r['workspace_id'], r['capability'], r['action'])
            assert sorted(actual_revocations, key=order) == sorted(data['permission_changes'], key=order), 'Approved grant revocations changed'
            cursor.execute('SELECT id,consumer_id,descriptor FROM mp_service_binding ORDER BY public_id FOR UPDATE')
            deleted, surviving = [], []
            for binding_id, consumer, descriptor in cursor.fetchall():
                if consumer in installation_ids or descriptor['provider_installation_id'] in public_ids:
                    deleted.append(binding_id)
                else:
                    surviving.append(descriptor)
            assert sorted(surviving, key=lambda b: b['binding_id']) == data['bindings'], 'Unrelated surviving binding changed'
            cursor.execute('DELETE FROM mp_service_binding WHERE id=ANY(%s)', [deleted])
            cursor.execute("UPDATE mp_plugin_grant SET state='revoked',policy_version=%s,write_date=timezone('UTC',now()) "
                           "WHERE installation_id=ANY(%s) AND state='approved'", [data['policy_version'], installation_ids])
            cursor.execute("UPDATE mp_workspace_plugin SET availability='suspended',write_date=timezone('UTC',now()) WHERE installation_id=ANY(%s)", [installation_ids])
            cursor.execute("UPDATE mp_plugin_installation SET state='removed',write_date=timezone('UTC',now()) WHERE id=ANY(%s)", [installation_ids])
            cursor.execute('UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=ANY(%s)', [sorted(workspaces)])
            inventory = 'sha256:' + hashlib.sha256(Path('/opt/modular/distribution-inventory.json').read_bytes()).hexdigest()
            for key, value in [('mp.release_generation', str(data['generation'])), ('mp.release_digest', data['release_digest']),
                               ('mp.last_operation_id', data['operation_id']), ('mp.active_inventory_digest', inventory)]:
                cursor.execute('''INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date)
                    VALUES (%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now())) ON CONFLICT(key)
                    DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date''', [key, value])
    connection.close()
    print(json.dumps(dict(metadata_published=True, operation_id=data['operation_id'], stable_tombstones_retained=True)))


if __name__ == '__main__': main()
