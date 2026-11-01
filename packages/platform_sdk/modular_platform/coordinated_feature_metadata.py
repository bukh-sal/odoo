"""Fixed native feature transaction after reviewed checkpoint/dispatch drain."""
import configparser,hashlib,json,sys
from pathlib import Path
from .feature_metadata import _feature_preimage,_feature_changes
from .plans import check_bundle,data_digest


def apply_coordinated_feature(cr,data):
    required={'bundle','base_state','metadata_digest','site_id','deployment_id','database','inventory_digest'}
    if not isinstance(data,dict) or set(data)!=required:raise ValueError('Exact coordinated feature payload required')
    bundle=data['bundle'];plan=bundle['plan'];lock=bundle['operation_lock'];base=data['base_state']
    check_bundle(bundle,base)
    if (plan['operation_type'] not in {'enable','suspend'} or not plan['backup']['required']
            or plan['site_ids']!=[data['site_id']] or plan['deployment_id']!=data['deployment_id']
            or not plan['artifacts'] or any(a['runtime']!='native' for a in plan['artifacts'])
            or lock['release']!=base['release_lock'] or lock['bindings']!=base.get('bindings',[])
            or lock.get('endpoints',[])!=base.get('endpoints',[])
            or data['inventory_digest']!=lock['release']['core_inventory_digest']
            or {'staged_image','platform_source_diff','native_core_changes','feature_states'}.intersection(lock)
            or any(t['site_id']!=data['site_id'] or t['action']!=plan['operation_type'] for t in lock['targets'])):
        raise ValueError('Checkpointed unchanged-release single-site native feature operation required')
    payload=dict(site_id=data['site_id'],operation_id=plan['operation_id'],plan_hash=bundle['plan_hash'],
        security_metadata_digest=base['security_metadata_digest'],targets=lock['targets'],
        permission_changes=plan['permission_changes'],policy_version=plan['policy_version'])
    site=_feature_preimage(cr,payload)
    cr.execute('SELECT current_database()')
    if cr.fetchone()!=(data['database'],):raise ValueError('Feature database changed')
    cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id'")
    if cr.fetchone()!=(data['deployment_id'],):raise ValueError('Feature deployment changed')
    if (data_digest(site)!=data['metadata_digest'] or site['release_digest']!=plan['base_release_digest']
            or site['active_inventory_digest']!=data['inventory_digest']):raise ValueError('Feature metadata preimage changed')
    cr.execute('SELECT site_id,release_digest,state FROM mp_dispatch_control FOR SHARE')
    if cr.fetchall()!=[(data['site_id'],plan['base_release_digest'],'paused')]:raise ValueError('Exact paused dispatch required')
    cr.execute("""SELECT count(*) FROM mp_job WHERE state IN ('running','outcome_unknown')
        OR (effect_mode='reconcile' AND effect_started AND state NOT IN ('completed','cancelled','dead_letter'))""")
    if cr.fetchone()[0]:raise ValueError('Unreconciled dispatch prevents feature mutation')
    cr.execute("SELECT count(*) FROM mp_event_delivery WHERE state='leased'")
    if cr.fetchone()[0]:raise ValueError('Outstanding event leases prevent feature mutation')
    _feature_changes(cr,site,payload)
    return dict(feature_metadata_published=True,operation_id=plan['operation_id'],native_maintenance=False,runtime_control=False)


def main():
    import psycopg2
    data=json.load(sys.stdin)
    inventory='sha256:'+hashlib.sha256(Path('/opt/modular/distribution-inventory.json').read_bytes()).hexdigest()
    if inventory!=data.get('inventory_digest'):raise ValueError('Feature child image inventory changed')
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');o=config['options']
    if o['db_name']!=data.get('database'):raise ValueError('Feature child database configuration changed')
    connection=psycopg2.connect(host=o['db_host'],port=o.getint('db_port'),user=o['db_user'],password=o['db_password'],dbname=o['db_name'],connect_timeout=10)
    try:
        with connection:
            with connection.cursor() as cr:result=apply_coordinated_feature(cr,data)
        print(json.dumps(result))
    finally:connection.close()


if __name__=='__main__':main()
