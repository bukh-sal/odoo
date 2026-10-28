"""Fixed maintenance child: atomic SDK feature availability, no native unload."""
import configparser
import json
import sys

import psycopg2
from psycopg2.extras import Json
from modular_platform.plans import data_digest
from modular_platform.metadata_sql import METADATA_SELECT


def main():
    data=json.load(sys.stdin)
    assert set(data)=={'site_id','operation_id','plan_hash','security_metadata_digest','targets'}
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],
        password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='15s'")
            cursor.execute('''LOCK TABLE mp_workspace,mp_membership,mp_principal,res_users,mp_plugin_installation,
                mp_workspace_plugin,mp_service_binding,mp_plugin_grant,ir_module_module IN SHARE ROW EXCLUSIVE MODE''')
            cursor.execute(METADATA_SELECT);site=cursor.fetchone()[0]
            assert site['site_id']==data['site_id'],'Feature target site changed'
            security=[{'site_id':site['site_id'],'workspaces':site['workspaces'],'memberships':site['memberships'],
                'grants':site['grants'],'bindings':site['bindings'],'native_modules':site['native_modules']}]
            assert data_digest(security)==data['security_metadata_digest'],'Current authority/bindings changed before metadata transaction'
            cursor.execute("SELECT to_regclass('mp_job'),to_regclass('mp_outbox')")
            assert cursor.fetchone()==(None,None),'Dispatch drain adapter is required before feature changes with durable work'
            affected=set()
            for target in data['targets']:
                assert target['site_id']==data['site_id'] and target['action'] in ('enable','suspend')
                cursor.execute('''SELECT f.id,w.id,w.state,i.state FROM mp_workspace_plugin f JOIN mp_workspace w ON w.id=f.workspace_id
                    JOIN mp_plugin_installation i ON i.id=f.installation_id WHERE w.public_id=%s AND i.public_id=%s AND i.plugin_id=%s''',
                    [target['workspace_id'],target['installation_id'],target['plugin_id']])
                row=cursor.fetchone();assert row and row[2:] == ('active','installed'),'Feature installation target changed'
                cursor.execute('UPDATE mp_workspace_plugin SET availability=%s,write_date=timezone(\'UTC\',now()) WHERE id=%s',
                    ['enabled' if target['action']=='enable' else 'suspended',row[0]])
                affected.add(row[1])
                cursor.execute('''INSERT INTO mp_audit_event(actor_id,workspace_public_id,plugin_id,action,target_id,decision,request_id,metadata,create_date)
                    VALUES (NULL,%s,%s,%s,%s,'allowed',%s,%s,timezone('UTC',now()))''',
                    [target['workspace_id'],target['plugin_id'],'operator.feature_'+target['action'],target['installation_id'],data['operation_id'],Json({'plan_hash':data['plan_hash']})])
            cursor.execute('UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=ANY(%s)',[list(affected)])
    connection.close()
    print(json.dumps({'feature_metadata_published':True,'operation_id':data['operation_id']}))


if __name__=='__main__':main()
