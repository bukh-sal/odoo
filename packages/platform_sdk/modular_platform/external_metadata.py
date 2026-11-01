"""Fixed metadata transaction for the independently approved external profile.

No native module, business schema, network request or runtime control is touched.
The host executor owns approval, OS endpoint revalidation, drain and checkpoints.
This module verifies the exact locked database preimage and publishes its metadata
in the caller's transaction. Importing/calling it does not confer OS authority.
"""
import configparser
import hashlib
import json
from pathlib import Path
import sys

from psycopg2.extras import Json
from .contracts import normalize_manifest,validate
from .metadata_sql import METADATA_SELECT
from .plans import check_bundle,data_digest


def apply_external_metadata(cr,data):
    required={'bundle','base_state','metadata_digest','plugins','site_id','deployment_id','database','inventory_digest'}
    if not isinstance(data,dict) or set(data)!=required:raise ValueError('Exact external metadata payload required')
    bundle=data['bundle'];plan=bundle['plan'];lock=bundle['operation_lock']
    check_bundle(bundle,data['base_state'])
    operation=plan['operation_type'];targets=lock['targets']
    if (operation not in {'install','upgrade','enable','suspend','unregister'} or not targets
            or plan['deployment_id']!=data['deployment_id'] or plan['site_ids']!=[data['site_id']]
            or any(t['site_id']!=data['site_id'] or t['action']!=operation for t in targets)
            or any(a['runtime']!='external_service' for a in plan['artifacts'])):
        raise ValueError('Exact single-site external metadata operation required')
    if data['inventory_digest']!=lock['release']['core_inventory_digest']:
        raise ValueError('Metadata publication cannot change native inventory')
    cr.execute("SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='20s'")
    cr.execute('''LOCK TABLE mp_workspace,mp_membership,mp_principal,res_users,mp_plugin_installation,
        mp_workspace_plugin,mp_service_binding,mp_plugin_grant,mp_service_credential,ir_module_module,
        ir_config_parameter IN SHARE ROW EXCLUSIVE MODE''')
    cr.execute('SELECT current_database()')
    if cr.fetchone()!=(data['database'],):raise ValueError('Metadata database changed')
    cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id'")
    if cr.fetchone()!=(data['deployment_id'],):raise ValueError('Metadata deployment changed')
    cr.execute(METADATA_SELECT);site=cr.fetchone()[0]
    if (site['site_id']!=data['site_id'] or data_digest(site)!=data['metadata_digest']
            or site['release_digest']!=plan['base_release_digest']
            or site['active_inventory_digest']!=data['inventory_digest']):
        raise ValueError('Metadata preimage changed before transaction')
    cr.execute('SELECT site_id,release_digest,state FROM mp_dispatch_control FOR SHARE')
    if cr.fetchall()!=[(data['site_id'],plan['base_release_digest'],'paused')]:
        raise ValueError('Exact paused dispatch required before metadata publication')
    cr.execute("""SELECT count(*) FROM mp_job WHERE state IN ('running','outcome_unknown')
        OR (effect_mode='reconcile' AND effect_started AND state NOT IN ('completed','cancelled','dead_letter'))""")
    if cr.fetchone()[0]:raise ValueError('Unreconciled dispatch prevents metadata mutation')
    cr.execute("SELECT count(*) FROM mp_event_delivery WHERE state='leased'")
    if cr.fetchone()[0]:raise ValueError('Outstanding event leases prevent metadata mutation')
    descriptors={r['plugin_id']:r for r in lock['release']['plugins']}
    states={(r['installation_id'],r['workspace_id']):r['availability'] for r in lock.get('feature_states',[])}
    if operation=='install' and set(states)!={(r['installation_id'],r['workspace_id']) for r in targets}:
        raise ValueError('Registration requires an explicit complete feature map')
    if operation!='install' and states:raise ValueError('Only registration can replace feature post-states')
    affected=set();workspaces=set();public_ids=set();actual_revocations=[]
    for target in targets:
        plugin=data['plugins'][target['plugin_id']];manifest=normalize_manifest(plugin['manifest'])
        selected=descriptors.get(target['plugin_id'])
        if (manifest['runtime']!={'kind':'external_service'} or not selected
                or selected['runtime']!='external_service' or selected['digest']!=plugin['digest']
                or selected['manifest_digest']!=data_digest(manifest)
                or manifest['plugin']['id']!=target['plugin_id']):
            raise ValueError('External metadata differs from selected trusted package')
        if any(name.startswith(('backend/','frontend/','migrations/')) for name in plugin.get('inventory',{})):
            raise ValueError('Executable code is forbidden in external metadata')
        cr.execute('SELECT id,state FROM mp_workspace WHERE public_id=%s FOR UPDATE',[target['workspace_id']])
        workspace=cr.fetchone()
        if not workspace:raise ValueError('Metadata workspace missing')
        cr.execute('''SELECT id,public_id,version,artifact_digest,state,runtime FROM mp_plugin_installation
            WHERE plugin_id=%s FOR UPDATE''',[target['plugin_id']]);row=cr.fetchone()
        availability=states.get((target['installation_id'],target['workspace_id']))
        if operation=='enable':availability='enabled'
        if operation=='suspend' or operation=='unregister':availability='suspended'
        if row:
            if row[1]!=target['installation_id'] or row[5]!='external_service':raise ValueError('Installation identity/runtime changed')
            installation=row[0]
            if operation=='install':
                if row[4]=='removed':
                    retained=[f for f in site['features'] if f['installation_id']==row[1]]
                    nominated={t['workspace_id'] for t in targets if t['installation_id']==row[1]}
                    if any(f['feature_state']!='suspended' or f['workspace_id'] not in nominated for f in retained):
                        raise ValueError('Re-registration omitted a retained scope')
                elif row[4]!='installed' or row[2:4]!=(manifest['plugin']['version'],plugin['digest']):
                    raise ValueError('Registration cannot replace existing artifact')
                cr.execute("UPDATE mp_plugin_installation SET state='installed',version=%s,artifact_digest=%s,manifest=%s WHERE id=%s",
                    [manifest['plugin']['version'],plugin['digest'],Json(manifest),installation])
            elif operation=='upgrade':
                prior=next(r for r in data['base_state']['release_lock']['plugins'] if r['plugin_id']==target['plugin_id'])
                if row[4]!='installed' or row[2:4] not in [(prior['version'],prior['digest']),(manifest['plugin']['version'],plugin['digest'])]:
                    raise ValueError('Upgrade metadata preimage changed')
                cr.execute('UPDATE mp_plugin_installation SET version=%s,artifact_digest=%s,manifest=%s WHERE id=%s',
                    [manifest['plugin']['version'],plugin['digest'],Json(manifest),installation])
            elif row[4]!='installed' or row[2:4]!=(manifest['plugin']['version'],plugin['digest']):
                raise ValueError('Lifecycle installation version/state changed')
        else:
            if operation!='install':raise ValueError('Lifecycle installation missing')
            cr.execute('''INSERT INTO mp_plugin_installation(public_id,plugin_id,version,artifact_digest,runtime,state,manifest,
                create_uid,write_uid,create_date,write_date) VALUES(%s,%s,%s,%s,'external_service','installed',%s,
                1,1,timezone('UTC',now()),timezone('UTC',now())) RETURNING id''',
                [target['installation_id'],target['plugin_id'],manifest['plugin']['version'],plugin['digest'],Json(manifest)])
            installation=cr.fetchone()[0]
        cr.execute('SELECT id,installation_id,availability FROM mp_workspace_plugin WHERE workspace_id=%s AND plugin_id=%s FOR UPDATE',
            [workspace[0],target['plugin_id']]);feature=cr.fetchone()
        if operation=='upgrade':
            if not feature or feature[1]!=installation:raise ValueError('Upgrade scope missing')
            availability=feature[2]
        if availability=='enabled' and workspace[1]!='active':raise ValueError('Inactive workspace cannot activate metadata')
        if feature:
            if feature[1]!=installation:raise ValueError('Feature ownership changed')
            if operation=='install' and any(f['installation_id']==target['installation_id'] and f['workspace_id']==target['workspace_id']
                    and f['metadata_state']!='removed' for f in data['base_state']['installations']):
                raise ValueError('Registration scope already present')
            cr.execute("UPDATE mp_workspace_plugin SET availability=%s,write_date=timezone('UTC',now()) WHERE id=%s",[availability,feature[0]])
        else:
            if operation!='install':raise ValueError('Lifecycle feature scope missing')
            cr.execute('''INSERT INTO mp_workspace_plugin(workspace_id,plugin_id,installation_id,availability,create_uid,write_uid,create_date,write_date)
                VALUES(%s,%s,%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now()))''',[workspace[0],target['plugin_id'],installation,availability])
        affected.add(installation);public_ids.add(target['installation_id']);workspaces.add(workspace[0])
        if operation=='unregister':
            retained={f['workspace_id'] for f in site['features'] if f['installation_id']==target['installation_id']}
            if retained!={t['workspace_id'] for t in targets if t['installation_id']==target['installation_id']}:
                raise ValueError('Unregistration omitted site workspace scopes')
    if operation=='unregister':
        for grant in site['grants']:
            if grant['installation_id'] in public_ids and grant['state']=='approved':
                target=next(t for t in targets if t['installation_id']==grant['installation_id'] and t['workspace_id']==grant['workspace_id'])
                actual_revocations.append(dict(plugin_id=target['plugin_id'],workspace_id=grant['workspace_id'],capability=grant['capability'],action='revoke'))
        if sorted(actual_revocations,key=data_digest)!=sorted(plan['permission_changes'],key=data_digest):
            raise ValueError('Unregistration grant preimage changed')
    desired={b['binding_id']:b for b in lock['bindings']}
    for binding in desired.values():
        validate('binding',binding)
        if binding['site_id']!=data['site_id'] or operation=='unregister' and (
                binding['consumer_installation_id'] in public_ids or binding['provider_installation_id'] in public_ids):
            raise ValueError('Binding cannot escape site or retain an unregistered installation')
        for public_id in [binding['consumer_installation_id'],binding['provider_installation_id']]:
            cr.execute('''SELECT i.id FROM mp_plugin_installation i JOIN mp_workspace_plugin f ON f.installation_id=i.id
                JOIN mp_workspace w ON w.id=f.workspace_id WHERE i.public_id=%s AND w.public_id=%s AND i.state='installed' ''',
                [public_id,binding['workspace_id']])
            if cr.fetchone() is None:raise ValueError('Binding installation/workspace ownership changed')
    cr.execute('SELECT id,consumer_id,descriptor FROM mp_service_binding ORDER BY public_id FOR UPDATE')
    for ident,consumer,binding in cr.fetchall():
        replacement=desired.pop(binding['binding_id'],None)
        relevant=consumer in affected or binding['provider_installation_id'] in public_ids
        if replacement==binding:continue
        if not relevant:raise ValueError('Metadata operation changed an unrelated binding')
        if replacement is None:cr.execute('DELETE FROM mp_service_binding WHERE id=%s',[ident])
        else:
            if any(replacement[k]!=binding[k] for k in ['binding_id','site_id','workspace_id','consumer_installation_id','alias']):
                raise ValueError('Binding immutable ownership changed')
            if replacement['generation']!=binding['generation']+1:raise ValueError('Binding generation changed')
            cr.execute('UPDATE mp_service_binding SET descriptor=%s WHERE id=%s',[Json(replacement),ident])
    for binding in desired.values():
        if binding['consumer_installation_id'] not in public_ids and binding['provider_installation_id'] not in public_ids:
            raise ValueError('New unrelated binding forbidden')
        cr.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s',[binding['consumer_installation_id']]);consumer=cr.fetchone()[0]
        cr.execute('SELECT id FROM mp_workspace WHERE public_id=%s',[binding['workspace_id']]);workspace=cr.fetchone()[0]
        cr.execute('''INSERT INTO mp_service_binding(public_id,workspace_id,consumer_id,alias,descriptor,state,create_uid,write_uid,create_date,write_date)
            VALUES(%s,%s,%s,%s,%s,'active',1,1,timezone('UTC',now()),timezone('UTC',now()))''',
            [binding['binding_id'],workspace,consumer,binding['alias'],Json(binding)])
    for change in plan['permission_changes']:
        target=next(t for t in targets if t['plugin_id']==change['plugin_id'] and t['workspace_id']==change['workspace_id'])
        if change['action']=='grant':
            requested={r['capability'] for r in data['plugins'][change['plugin_id']]['manifest']['permissions']['requests']}
            if change['capability'] not in requested or operation not in ('install','upgrade','enable'):
                raise ValueError('Undeclared or unavailable metadata grant')
            cr.execute('''SELECT f.availability FROM mp_workspace_plugin f JOIN mp_workspace w ON w.id=f.workspace_id
                JOIN mp_plugin_installation i ON i.id=f.installation_id WHERE i.public_id=%s AND w.public_id=%s''',
                [target['installation_id'],target['workspace_id']])
            if cr.fetchone()!=('enabled',):raise ValueError('Suspended metadata feature cannot receive grants')
        elif change['action']!='revoke' or operation!='unregister':raise ValueError('Unexpected metadata revocation')
        cr.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s',[target['installation_id']]);installation=cr.fetchone()[0]
        cr.execute('SELECT id FROM mp_workspace WHERE public_id=%s',[target['workspace_id']]);workspace=cr.fetchone()[0]
        cr.execute('''INSERT INTO mp_plugin_grant(installation_id,workspace_id,capability,state,policy_version,create_uid,write_uid,create_date,write_date)
            VALUES(%s,%s,%s,%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now()))
            ON CONFLICT(installation_id,workspace_id,capability) DO UPDATE SET state=EXCLUDED.state,policy_version=EXCLUDED.policy_version''',
            [installation,workspace,change['capability'],'approved' if change['action']=='grant' else 'revoked',plan['policy_version']])
    if operation=='unregister':
        cr.execute("UPDATE mp_service_credential SET state='revoked' WHERE installation_public_id=ANY(%s) AND state='active'",[sorted(public_ids)])
        cr.execute("UPDATE mp_plugin_installation SET state='removed' WHERE id=ANY(%s)",[sorted(affected)])
    cr.execute('UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=ANY(%s)',[sorted(workspaces)])
    for target in targets:
        cr.execute('''INSERT INTO mp_audit_event(actor_id,workspace_public_id,plugin_id,action,target_id,decision,request_id,metadata,create_date)
            VALUES(NULL,%s,%s,%s,%s,'allowed',%s,%s,timezone('UTC',now()))''',
            [target['workspace_id'],target['plugin_id'],'operator.external_'+operation,target['installation_id'],plan['operation_id'],Json({'plan_hash':bundle['plan_hash']})])
    for key,value in [('mp.release_generation',str(lock['release']['generation'])),('mp.release_digest',plan['target_release_digest']),
            ('mp.last_operation_id',plan['operation_id']),('mp.active_inventory_digest',data['inventory_digest'])]:
        cr.execute('''INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date)
            VALUES(%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now())) ON CONFLICT(key)
            DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date''',[key,value])
    return dict(metadata_published=True,operation_id=plan['operation_id'],native_maintenance=False,runtime_control=False)


def main():
    import psycopg2
    data=json.load(sys.stdin)
    inventory='sha256:'+hashlib.sha256(Path('/opt/modular/distribution-inventory.json').read_bytes()).hexdigest()
    if inventory!=data.get('inventory_digest'):raise ValueError('Metadata child inventory differs from approved image')
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
    if options['db_name']!=data.get('database'):raise ValueError('Metadata child database configuration changed')
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],
        password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
    try:
        with connection:
            with connection.cursor() as cr:result=apply_external_metadata(cr,data)
        print(json.dumps(result))
    finally:connection.close()


if __name__=='__main__':main()
