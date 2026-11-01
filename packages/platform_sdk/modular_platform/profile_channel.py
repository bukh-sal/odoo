"""OS-only sanitized planning-cache output; carries no approval authority."""
from datetime import datetime,timezone
import json
from .deployment import _run
from .contracts import load_json
from .operator_os import OperatorError
from .projection import public_profile

PROFILE_WRITER='import configparser,json,sys\nimport psycopg2\nfrom psycopg2.extras import Json\nfrom modular_platform.plans import data_digest\npayload=json.load(sys.stdin)\nconfig=configparser.ConfigParser();config.read(\'/run/secrets/odoo_config\');options=config[\'options\']\nconnection=psycopg2.connect(host=options[\'db_host\'],port=options.getint(\'db_port\'),user=options[\'db_user\'],password=options[\'db_password\'],dbname=options[\'db_name\'],connect_timeout=10)\nwith connection:\n with connection.cursor() as cursor:\n  cursor.execute("SELECT value FROM ir_config_parameter WHERE key=\'mp.site_id\'");site=cursor.fetchone()[0]\n  assert site in payload[\'configuration\'][\'site_ids\'],\'Public profile must match the current site\'\n  if \'published_release\' in payload[\'configuration\']:\n   cursor.execute("SELECT key,value FROM ir_config_parameter WHERE key IN (\'mp.release_generation\',\'mp.release_digest\',\'mp.active_inventory_digest\') FOR SHARE")\n   actual=dict(cursor.fetchall())\n   expected={\'mp.release_generation\':str(payload[\'configuration\'][\'generation\']),\'mp.release_digest\':data_digest(payload[\'configuration\'][\'published_release\']),\'mp.active_inventory_digest\':payload[\'runtime\'][\'inventory_digest\']}\n   assert actual==expected,\'Database publication changed before planning profile transaction\'\n  cursor.execute("INSERT INTO mp_operation_profile(site_public_id,payload,create_uid,write_uid,create_date,write_date) VALUES (%s,%s,1,1,timezone(\'UTC\',now()),timezone(\'UTC\',now())) ON CONFLICT(site_public_id) DO UPDATE SET payload=EXCLUDED.payload,write_uid=1,write_date=timezone(\'UTC\',now())",[site,Json(payload)])\nconnection.close()\nprint(json.dumps({\'profile_published\':True,\'site_id\':site}))\n'


def publish_profile(observer,catalog,*,staged=None):
    observation=observer.read();snapshot=catalog.snapshot()
    state=observer.state(observation,snapshot)['state']
    if 'published_release' in observer.config and observation['runtime'].get('published_release_protocol')!=1:
        raise OperatorError('Selected image lacks the published-release profile reader; preserve the old cache until an approved compatible image is deployed')
    payload=public_profile(observer.config,observation,snapshot,datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    if staged is not None:
        from .manager_planning import candidate_preview
        from .projection import runtime_inputs
        descriptor,record=staged
        if record['base_configuration']!=observer.config:
            raise OperatorError('Staged preview base configuration changed before publication')
        external=[p for p in state['release_lock']['plugins'] if p['runtime']=='external_service']
        runtime_inputs(record['runtime'],snapshot,external_plugins=external)
        payload['staged_release']=candidate_preview(descriptor,record['runtime'],observer.config['image_id'])
    raw=json.dumps(payload).encode()
    if len(raw)>16*1024*1024:raise OperatorError('Public planning profile size limit')
    result=load_json(_run(['docker','exec','-i',observer._container('app'),'/venv/bin/python','-c',PROFILE_WRITER],input=raw))
    if result.get('profile_published') is not True:raise OperatorError('Sanitized planning profile publication was not confirmed')
    return result|{'release_digest':state['release_digest'],'catalog_validation_digest':state.get('catalog_validation_digest')}
