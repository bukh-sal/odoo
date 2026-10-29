"""Fixed source-removal publisher: retain history and publish the new epoch.

Run only by the independently approved executor under maintenance/checkpoint.
No native registry imports, package hooks, schema/data deletion or row creation
for never-installed packages. Targets are identities, never code or SQL.
"""
import configparser
import hashlib
import json
from pathlib import Path
import sys
from uuid import UUID, uuid5


def main():
    import psycopg2
    data=json.load(sys.stdin)
    assert set(data)=={'site_id','deployment_id','operation_id','generation','release_digest','targets','plugins','bindings',
                       'permission_changes','previous_plugins','database','policy_version'}
    assert data['targets'] and not data['permission_changes']
    assert all(t['action']=='remove' and t['site_id']==data['site_id'] for t in data['targets'])
    removed={t['plugin_id'] for t in data['targets']}
    assert removed <= data['previous_plugins'].keys() and not removed & data['plugins'].keys()
    raw=(Path('/opt/modular')/'distribution-inventory.json').read_bytes();inventory=json.loads(raw)
    assert set(inventory.get('artifacts',{}))==set(data['plugins'])
    assert not any(data['previous_plugins'][p]['native_addon'] in inventory['native_addons'] for p in removed)
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
    assert options['db_name']==data['database'],'Removal publication target mismatch'
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],
        password=options['db_password'],dbname=data['database'],connect_timeout=10)
    with connection:
        with connection.cursor() as cursor:
            for key,value in [('mp.site_id',data['site_id']),('mp.deployment_id',data['deployment_id']),('mp.release_generation',str(data['generation']-1))]:
                cursor.execute('SELECT value FROM ir_config_parameter WHERE key=%s',[key]);assert cursor.fetchone()==(value,),'Removal base identity changed'
            cursor.execute("SELECT to_regclass('mp_job'),to_regclass('mp_outbox')");assert cursor.fetchone()==(None,None),'Unsupported dispatch needs G6 reconciliation'
            for plugin in sorted(removed):
                targets=[t for t in data['targets'] if t['plugin_id']==plugin]
                assert len({t['workspace_id'] for t in targets})==len(targets)
                cursor.execute('SELECT id,public_id,state,manifest FROM mp_plugin_installation WHERE plugin_id=%s FOR UPDATE',[plugin])
                row=cursor.fetchone();addons={data['previous_plugins'][plugin]['native_addon']}
                if row:
                    installation,public_id,state,manifest=row
                    assert state=='removed' and all(t['installation_id']==public_id for t in targets),'Retained installation is not inert'
                    addons.add(manifest['runtime']['addon_name'])
                    cursor.execute('SELECT w.public_id,f.availability FROM mp_workspace_plugin f JOIN mp_workspace w ON w.id=f.workspace_id WHERE f.installation_id=%s ORDER BY w.public_id',[installation])
                    features=cursor.fetchall()
                    assert all(a=='suspended' for w,a in features)
                    assert not features or {w for w,a in features}=={t['workspace_id'] for t in targets},'Removal omitted retained scopes'
                    cursor.execute("SELECT count(*) FROM mp_plugin_grant WHERE installation_id=%s AND state='approved'",[installation]);assert cursor.fetchone()==(0,),'Removal retained approved grant'
                else:
                    public_id=str(uuid5(UUID(data['site_id']),'plugin:'+plugin))
                    assert all(t['installation_id']==public_id for t in targets),'Never-installed nomination identity mismatch'
                cursor.execute('SELECT count(*) FROM mp_workspace WHERE public_id=ANY(%s)',[[t['workspace_id'] for t in targets]])
                assert cursor.fetchone()==(len(targets),),'Unknown removal workspace context'
                cursor.execute("SELECT count(*) FROM ir_module_module WHERE name=ANY(%s) AND state IN ('installed','to install','to upgrade','to remove')",[sorted(addons)])
                assert cursor.fetchone()==(0,),'Native module still needs removed source'
                cursor.execute('SELECT descriptor FROM mp_service_binding')
                for (binding,) in cursor.fetchall():
                    assert (binding['consumer_installation_id']!=public_id and binding['provider_installation_id']!=public_id
                            and binding['provider_plugin_id']!=plugin),'Removal retained live binding'
            cursor.execute('SELECT descriptor FROM mp_service_binding ORDER BY public_id')
            assert [r[0] for r in cursor.fetchall()]==data['bindings'],'Surviving bindings changed before publication'
            for key,value in [('mp.release_generation',str(data['generation'])),('mp.release_digest',data['release_digest']),
                              ('mp.last_operation_id',data['operation_id']),('mp.active_inventory_digest','sha256:'+hashlib.sha256(raw).hexdigest())]:
                cursor.execute('''INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date)
                    VALUES (%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now()))
                    ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date''',[key,value])
    connection.close()
    print(json.dumps(dict(metadata_published=True,operation_id=data['operation_id'],retained_history_unchanged=True,plugin_data_not_deleted=True)))


if __name__=='__main__':main()
