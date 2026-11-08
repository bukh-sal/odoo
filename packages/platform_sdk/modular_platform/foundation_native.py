"""Fixed independent operator child for the single owned46→47 recipe.

Executed from reviewed host bytes under either exact image. No package hooks,
caller SQL, executable paths or arbitrary model methods are accepted.
"""
import configparser
import hashlib
import json
from pathlib import Path
import sys
from uuid import UUID


def main():
    data=json.load(sys.stdin)
    declaration=data['declaration'];effect=declaration['site_effects'][0]
    assert str(UUID(data['operation_id']))==data['operation_id']
    assert declaration['recipe']=='owned-addon-extraction-46-47-v1'
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config')
    options=config['options'];assert options['db_name']==data['database']
    inventory=Path('/opt/modular/distribution-inventory.json').read_bytes()
    phase=data['phase'];assert phase in ('retire','archive')
    side=declaration['source' if phase=='retire' else 'target']
    assert 'sha256:'+hashlib.sha256(inventory).hexdigest()==side['inventory_digest']
    import odoo
    from odoo import api,SUPERUSER_ID
    from odoo.modules.registry import Registry
    odoo.tools.config.parse_config(['-c','/run/secrets/odoo_config','-d',data['database'],
        '--no-http','--workers=0','--max-cron-threads=0','--without-demo'])
    registry=Registry.new(data['database'])
    with registry.cursor() as cursor:
        env=api.Environment(cursor,SUPERUSER_ID,{})
        assert env['ir.config_parameter'].sudo().get_param('mp.deployment_id')==data['deployment_id']
        if phase=='retire':
            cursor.execute("SELECT name,latest_version FROM ir_module_module WHERE state='installed' ORDER BY name")
            assert dict(cursor.fetchall())=={m['addon']:m['version'] for m in effect['native_modules']}
            for row in effect['iap_tables']+effect['retained_tables']:
                # Names have been whitelisted by the host; child also refuses all others.
                assert row['table'] in ('iap_account','iap_account_res_company_rel','iap_account_res_users_rel',
                    'iap_service','discuss_channel','fetchmail_server','mail_message','maintenance_request',
                    'mp_aurora_task','mp_aurora_task_list','mp_aurora_task_list_res_users_rel','mp_aurora_task_stage')
                cursor.execute('SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb)::text FROM "'+row['table']+'" t')
                payload=cursor.fetchone()[0]
                assert hashlib.sha256(payload.encode()).hexdigest()==row['sha256'] and len(json.loads(payload))==row['rows']
            module=env['ir.module.module'].search([('name','=','iap'),('state','=','installed')])
            assert len(module)==1 and not module.downstream_dependencies(), 'IAP retirement cannot remove any dependent module'
            module.button_immediate_uninstall()
            # The API can commit and rebuild its registry. Any subsequent failure
            # remains an uncertain operation requiring independent restore.
            cursor.commit()
        else:
            assert len(data['payloads'])==4
            for row in effect['iap_tables']:
                payload=data['payloads'][row['table']]
                assert hashlib.sha256(payload.encode()).hexdigest()==row['sha256'] and len(json.loads(payload))==row['rows']
                cursor.execute('INSERT INTO mp_retirement_archive (operation_id,recipe,source_image,source_inventory,table_name,row_count,sha256,payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                    [data['operation_id'],declaration['recipe'],declaration['source']['image_id'],declaration['source']['inventory_digest'],row['table'],row['rows'],row['sha256'],payload])
            # Retain our published R1 references after new owners have loaded.
            for row in effect['mail_ownership']:
                adopted=env['ir.model.data'].search([('module','=',row['owner']),('name','=',row['name'])])
                assert len(adopted)==1 and adopted.model==row['model'] and adopted.res_id==row['res_id']
                assert not env['ir.model.data'].search([('module','=','mail'),('name','=',row['name'])])
                env['ir.model.data'].create(dict(module='mail',name=row['name'],model=row['model'],res_id=row['res_id'],noupdate=True))
        cursor.commit()
    if phase=='retire':
        # Fresh environment after supported uninstall; move identities before
        # target module updates can remove stale old-owner records.
        registry=Registry.new(data['database'])
        with registry.cursor() as cursor:
            env=api.Environment(cursor,SUPERUSER_ID,{})
            for row in effect['mail_ownership']:
                record=env['ir.model.data'].search([('module','=','mail'),('name','=',row['name'])])
                assert len(record)==1 and record.model==row['model'] and record.res_id==row['res_id']
                assert not env['ir.model.data'].search([('module','=',row['owner']),('name','=',row['name'])])
                record.write({'module':row['owner']})
            cursor.commit()
    print(json.dumps(dict(kind='foundation_transition_effect',phase=phase,operation_id=data['operation_id'],
        archived_tables=4 if phase=='archive' else 0,adopted_ids=len(effect['mail_ownership']))),flush=True)


if __name__=='__main__':main()
