"""Actual same-process Odoo registry/data/context checks; all writes rollback."""
import configparser
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys

DATA=json.loads(sys.argv[1])
root=Path('/opt/modular');inventory=root/'distribution-inventory.json'
spec=importlib.util.spec_from_file_location('verified_tenant_guard',root/'packages/platform_sdk/modular_platform/worker_start.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
import psycopg2
checks=[]
for case in DATA['order']:
    cfg=configparser.ConfigParser();cfg.read('/cases/'+case+'/config/odoo_config');options=cfg['options']
    connection=psycopg2.connect(host=options['db_host'],user=options['db_user'],password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
    connection.set_session(readonly=True,autocommit=True)
    try:guard.validate(root,options,connection,DATA['cases'][case]['database'],DATA['inventory_digest'])
    finally:connection.close()
    checks.append('preimport_guard_'+case)

import odoo.init
from odoo.tools import config
from odoo.modules import initialize_sys_path
config.parse_config(['-c','/cases/a/config/odoo_config','--no-http','--workers=0','--max-cron-threads=0'])
initialize_sys_path()
from odoo.orm.registry import Registry
from odoo import api
from odoo.exceptions import AccessError
registries={}
for case in DATA['order']:
    db=DATA['cases'][case]['database'];registries[case]=Registry(db)
    assert registries[case].ready and registries[case].db_name==db
    assert ('x_notes_labels' in registries[case]['mp.example.note']._fields)==(case=='a')
assert registries['a'] is not registries['b']
assert registries['a']['mp.example.note'] is not registries['b']['mp.example.note']
assert 'odoo.addons.mp_example_notes_labels' in sys.modules
assert 'x_notes_labels' not in registries['b']['mp.example.note']._fields
checks.extend(['distinct_registry_and_model_classes','extension_import_does_not_leak_to_uninstalled_registry'])
from odoo.addons.mp_identity.scopes import scoped_environment,resolve_scope
from odoo.addons.mp_core.dispatch import CallFrame,call_bound


def environment(cr,case):return scoped_environment(api.Environment(cr,DATA['uid'],{}),DATA['workspace'])


def read(case):
    cfg=DATA['cases'][case];registry=registries[case]
    assert Registry(cfg['database']) is registry
    with registry.cursor() as cr:
        env=environment(cr,case);note=env['mp.example.note'].browse(DATA['note']['id']);value=note.read(['public_id','title','revision'])[0]
        assert value['public_id']==DATA['note']['public_id'] and value['title']=='TEN_'+case.upper()+'_VISIBLE'
        assert env['ir.config_parameter'].sudo().get_param('mp.site_id')==cfg['site_id']
        assert env.registry is registry and env.cr.dbname==cfg['database']
        assert note.search_count([])==2
        cr.rollback()
        return dict(case=case,database=cfg['database'],title=value['title'],site_id=cfg['site_id'])


for _ in range(4):
    for case in DATA['order']:read(case)
checks.append('alternating_colliding_record_ids_and_config_cache')
with ThreadPoolExecutor(max_workers=4) as pool:concurrent=list(pool.map(read,['a','b']*16))
assert len(concurrent)==32;checks.append('32_concurrent_cross_database_reads')

# Keep both cursors/record caches alive. Warm the same integer/public IDs, then
# mutate one transaction with its actor/CAS and prove the other cache and SQL
# remain in its own database. Roll back each test transaction explicitly.
with registries['a'].cursor() as ca,registries['b'].cursor() as cb:
    ea=environment(ca,'a');eb=environment(cb,'b');na=ea['mp.example.note'].browse(DATA['note']['id']);nb=eb['mp.example.note'].browse(DATA['note']['id'])
    assert na.title=='TEN_A_VISIBLE' and nb.title=='TEN_B_VISIBLE';ra=na.revision;rb=nb.revision
    na.with_context(expected_revision=ra).write({'title':'TEN_A_ROLLBACK_ONLY'})
    assert na.title=='TEN_A_ROLLBACK_ONLY' and nb.title=='TEN_B_VISIBLE' and nb.revision==rb
    cb.execute('SELECT title,revision FROM mp_example_note WHERE id=%s',[nb.id]);assert cb.fetchone()==('TEN_B_VISIBLE',rb)
    nb.with_context(expected_revision=rb).write({'title':'TEN_B_ROLLBACK_ONLY'})
    assert nb.title=='TEN_B_ROLLBACK_ONLY' and na.title=='TEN_A_ROLLBACK_ONLY' and na.revision==ra+1
    na.flush_recordset(['title','revision'])
    ca.execute('SELECT title,revision FROM mp_example_note WHERE id=%s',[na.id]);assert ca.fetchone()==('TEN_A_ROLLBACK_ONLY',ra+1)
    # Equal user/workspace/principal IDs cannot make an A Scope authoritative in B.
    for target,previous in [(eb,resolve_scope(ea,DATA['workspace'])),(ea,resolve_scope(eb,DATA['workspace']))]:
        try:target(context={**target.context,'_mp_scope':previous})['mp.example.note'].browse(DATA['note']['id']).read(['title'])
        except AccessError as error:assert 'Actor or site context mismatch' in str(error)
        else:raise AssertionError('Foreign typed scope crossed databases')
    # Imported shared service registrations do not make a different site's
    # actor/provider frame valid against the target DB's own binding record.
    scope=resolve_scope(eb,DATA['workspace']);frame=CallFrame(scope.principal_public_id,scope.workspace_public_id,DATA['cases']['a']['site_id'],DATA['notes_installation'],'org.example.notes',())
    try:call_bound(eb(context={**eb.context,'_mp_call_frame':frame}),'documents','get',{'note_id':DATA['note']['public_id']})
    except AccessError as error:assert 'Provider chain identity mismatch' in str(error)
    else:raise AssertionError('Foreign site frame accepted')
    ca.rollback();cb.rollback()
checks.extend(['independent_ORM_cache_and_CAS_transactions','foreign_typed_scope_denied_both_directions','foreign_site_service_frame_denied','writes_rolled_back'])
for case in ['a','b']:read(case)
print('MP_TEN_RESULT='+json.dumps(dict(result='passed',order=DATA['order'],checks=checks,concurrent_reads=len(concurrent),same_process=True,registry_class_ids={case:id(registries[case]) for case in ['a','b']},native_extension_imported=True,labels_field_a=True,labels_field_b=False,all_test_writes_rolled_back=True)),flush=True)
