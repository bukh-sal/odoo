"""Read-only fixed data witnesses for the independently approved Tasks transition.

No caller SQL, migrations, application imports or commits. Raw payloads belong
only in the protected operator checkpoint area, never Docker/public logs.
"""
from __future__ import annotations

import configparser
import hashlib
import json
from pathlib import Path
import sys

TASK_COLUMNS = {
    'mp_aurora_task': ('id','name','description','list_id','stage_id','creator_id','assignee_id','due_date','active','create_uid','write_uid','create_date','write_date'),
    'mp_aurora_task_list': ('id','name','description','owner_id','active','create_uid','write_uid','create_date','write_date'),
    'mp_aurora_task_list_res_users_rel': ('mp_aurora_task_list_id','res_users_id'),
    'mp_aurora_task_stage': ('id','name','list_id','sequence','done','create_uid','write_uid','create_date','write_date'),
}
MAINTENANCE_TABLES = ('maintenance_equipment','maintenance_request','maintenance_team')
APP = 'mp_aurora_tasks'
PLUGIN = 'dev.aurora.tasks'


def payload(cr, table, *, old_stage_ids=None):
    if table not in (*TASK_COLUMNS, *MAINTENANCE_TABLES):
        raise ValueError('Unreviewed application witness table')
    columns = ','.join(TASK_COLUMNS[table]) if table in TASK_COLUMNS else '*'
    where = ' WHERE id=ANY(%s)' if old_stage_ids is not None else ''
    cr.execute("SELECT COALESCE(jsonb_agg(to_jsonb(r) ORDER BY to_jsonb(r)::text),'[]'::jsonb)::text "
               'FROM (SELECT '+columns+' FROM '+table+where+') r',
               [old_stage_ids] if old_stage_ids is not None else None)
    return cr.fetchone()[0]


def _tables(cr, modules):
    names = sorted([*(TASK_COLUMNS if APP in modules else []),
                    *(MAINTENANCE_TABLES if 'maintenance' in modules else [])])
    for name in TASK_COLUMNS:
        cr.execute('SELECT to_regclass(%s) IS NOT NULL', ['public.'+name])
        if cr.fetchone()[0] != (APP in modules):
            raise ValueError('Source Tasks native state and retained schema disagree')
        if APP in modules:
            cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",[name])
            if {r[0] for r in cr.fetchall()} != set(TASK_COLUMNS[name]):
                raise ValueError('Source Tasks columns differ from the reviewed native0.1.0 schema')
    return names


def _modules(cr):
    cr.execute("SELECT count(*) FROM ir_module_module WHERE state IS NULL OR state NOT IN ('installed','uninstalled','uninstallable')")
    if cr.fetchone()[0]:raise ValueError('Pending native module transitions require reconciliation before adoption')
    cr.execute("SELECT name,state,latest_version FROM ir_module_module WHERE state='installed' ORDER BY name")
    return [dict(addon=n,state=s,version=v) for n,s,v in cr.fetchall()]


def _metadata_absent(cr):
    cr.execute("SELECT count(*) FROM mp_plugin_installation WHERE plugin_id=%s "
               "OR manifest->'runtime'->>'addon_name'=%s", [PLUGIN,APP])
    if cr.fetchone()[0]:raise ValueError('Adoption requires unregistered native Tasks')
    cr.execute('SELECT count(*) FROM mp_workspace_plugin WHERE plugin_id=%s',[PLUGIN])
    if cr.fetchone()[0]:raise ValueError('Legacy native Tasks cannot already have workspace feature state')


def capture(cr, site_id):
    _metadata_absent(cr)
    for table in ('mp_aurora_reminder','mp_aurora_notification'):
        cr.execute('SELECT to_regclass(%s) IS NOT NULL',['public.'+table])
        if cr.fetchone()[0]:raise ValueError('Legacy native0.1.0 source already has unreviewed reminder schema')
    for table in ('mp_job','mp_job_identity'):
        cr.execute('SELECT count(*) FROM '+table+' WHERE workspace_id IS NULL')
        if cr.fetchone()[0]:raise ValueError('Sealed47 cannot already contain native-scope job rows')
    modules = _modules(cr)
    names = {r['addon']:r['version'] for r in modules}
    tables = _tables(cr,names)
    payloads = {name:payload(cr,name) for name in tables}
    witnesses = [dict(table=n,rows=len(json.loads(value)),sha256=hashlib.sha256(value.encode('utf8')).hexdigest())
                 for n,value in payloads.items()]
    gaps = []
    if APP in names:
        cr.execute("""SELECT l.id,k.done FROM mp_aurora_task_list l
            CROSS JOIN (VALUES(false),(true)) k(done)
            WHERE NOT EXISTS(SELECT 1 FROM mp_aurora_task_stage s WHERE s.list_id=l.id AND s.done=k.done)
            ORDER BY l.id,k.done""")
        gaps = [dict(list_id=ident,done=done) for ident,done in cr.fetchall()]
    return dict(effect=dict(site_id=site_id,native_modules=modules,tasks_installed=APP in names,
                            retained_tables=witnesses,stage_additions=gaps),payloads=payloads)


def verify(cr, effect, baseline):
    _metadata_absent(cr)  # The normal metadata child runs only after these checks.
    expected = {r['addon']:r['version'] for r in effect['native_modules']}
    expected['mp_core'] = '19.0.0.1.49'
    if effect['tasks_installed']:expected[APP]='19.0.0.2.2'
    actual = {r['addon']:r['version'] for r in _modules(cr)}
    if actual != expected:raise ValueError('Transition installed native modules differ from approval')
    if set(baseline) != {r['table'] for r in effect['retained_tables']}:
        raise ValueError('Private application witness coverage differs')
    for witness in effect['retained_tables']:
        table = witness['table']; old = baseline[table]
        if (len(json.loads(old)) != witness['rows']
                or hashlib.sha256(old.encode('utf8')).hexdigest() != witness['sha256']):
            raise ValueError('Private baseline does not match reviewed witness')
        if table == 'mp_aurora_task_stage':
            rows = json.loads(old)
            ids = [r['id'] for r in rows]
            old_ids=set(ids)
            if any(type(n) is not int or n<=0 for n in ids):raise ValueError('Invalid retained stage identity')
            now = payload(cr,table,old_stage_ids=ids)
            if now != old:raise ValueError('Existing stage values/identities changed')
            added = [r for r in json.loads(payload(cr,table)) if r['id'] not in old_ids]
            pairs = [(r['list_id'],r['done']) for r in added]
            approved = [(r['list_id'],r['done']) for r in effect['stage_additions']]
            if len(pairs)!=len(approved) or set(pairs)!=set(approved):
                raise ValueError('New stages differ from previously missing choices')
            for row in added:
                if (row['name'] != ('Done' if row['done'] else 'To do')
                        or row['sequence'] != (20 if row['done'] else 10)
                        or row['create_uid'] != 1 or row['write_uid'] != 1):
                    raise ValueError('Unreviewed added stage contents')
        elif payload(cr,table) != old:
            raise ValueError('Retained application data changed: '+table)
    if effect['tasks_installed']:
        cr.execute("SELECT count(*) FROM mp_aurora_task WHERE reminder IS DISTINCT FROM 'none' OR reminder_revision IS DISTINCT FROM 1")
        if cr.fetchone()[0]:raise ValueError('Legacy tasks gained unsolicited reminders')
        for table in ('mp_aurora_reminder','mp_aurora_notification'):
            cr.execute('SELECT count(*) FROM '+table)
            if cr.fetchone()[0]:raise ValueError('New reminder storage must be empty before publication')
    else:
        # An available archive cannot silently install the absent application.
        _tables(cr,actual)
        for table in ('mp_aurora_reminder','mp_aurora_notification'):
            cr.execute('SELECT to_regclass(%s) IS NOT NULL',['public.'+table])
            if cr.fetchone()[0]:raise ValueError('Absent Tasks gained reminder schema')
    return dict(native_modules=actual,retained_tables=effect['retained_tables'],
                added_stage_choices=len(effect['stage_additions']),legacy_reminders_disabled=True)


def main():
    import psycopg2
    data=json.load(sys.stdin)
    if set(data) not in ({'phase','database','site_id','deployment_id','effect'},
                        {'phase','database','site_id','deployment_id','effect','payloads'}):
        raise ValueError('Exact private witness input required')
    if data['phase'] not in {'observe','capture','verify'}:raise ValueError('Read-only witness phase required')
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config')
    settings=config['options']
    if settings['db_name']!=data['database']:raise ValueError('Witness database differs from mounted target')
    with psycopg2.connect(host=settings['db_host'],port=settings['db_port'],user=settings['db_user'],
                          password=settings['db_password'],dbname=data['database']) as conn:
        conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
        with conn.cursor() as cr:
            cr.execute("SET LOCAL statement_timeout='30s'")
            cr.execute("SELECT key,value FROM ir_config_parameter WHERE key IN ('mp.site_id','mp.deployment_id')")
            if dict(cr.fetchall())!={'mp.site_id':data['site_id'],'mp.deployment_id':data['deployment_id']}:
                raise ValueError('Witness site/deployment changed')
            if data['phase'] in {'observe','capture'}:
                value=capture(cr,data['site_id'])
                if data['phase']=='capture' and value['effect']!=data['effect']:
                    raise ValueError('Application data changed since independent review')
                if data['phase']=='observe':value={'effect':value['effect']}
            else:value=verify(cr,data['effect'],data['payloads'])
    print(json.dumps(value,ensure_ascii=True))


if __name__=='__main__':main()
