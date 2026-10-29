"""Explicit operator-run account rotation on a newly owned qualification copy."""
import configparser
import json
from pathlib import Path
import runpy

cfg=configparser.ConfigParser();cfg.read('/run/secrets/odoo_config');options=cfg['options']
import psycopg2
guard=runpy.run_path('/opt/modular/packages/platform_sdk/modular_platform/worker_start.py')
connection=psycopg2.connect(host=options['db_host'],user=options['db_user'],password=options['db_password'],dbname=options['db_name'])
connection.set_session(readonly=True,autocommit=True)
try:guard['validate']('/opt/modular',options,connection,data['database'],data['inventory_digest'])
finally:connection.close()
import odoo.init
from odoo import api,SUPERUSER_ID
from odoo.tools import config
from odoo.modules import initialize_sys_path
from odoo.orm.registry import Registry
config.parse_config(['-c','/run/secrets/odoo_config','--no-http','--workers=0','--max-cron-threads=0']);initialize_sys_path()
registry=Registry(data['database'])
with registry.cursor() as cr:
    # Explicit fixture provisioning under local operator authority. This is not
    # an HTTP elevation or an application-supplied migration/installation hook.
    env=api.Environment(cr,SUPERUSER_ID,{})
    for row in data['accounts'].values():env['res.users'].browse(row['id']).write({'login':row['login'],'password':row['password']})
    env['res.users'].search([('login','=like','g5_%')]).write({'active':False})
    env['res.users'].search([('login','=','admin')]).write({'active':False,'password':data['retired_admin_password']})
    env['ir.config_parameter'].set_param('web.base.url',data['origin'])
    env['ir.config_parameter'].set_param('web.base.url.freeze','True')
    cr.execute("UPDATE mp_service_credential SET state='revoked'")
    cr.commit()
    cr.execute("SELECT count(*) FROM res_users WHERE active AND (login='admin' OR login LIKE 'g5_%%')")
    assert cr.fetchone()==(0,)
print(json.dumps(dict(result='rotated_explicit_accounts_and_disabled_shipped_logins',account_count=len(data['accounts']),old_admin_and_fixture_logins_inactive=True,technical_credentials_revoked=True)),flush=True)
