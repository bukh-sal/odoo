"""Fixed private child for the independently authorized host dispatch adapter.

LIFECYCLE_SOURCE is prepended by the host from its own locked implementation;
it is never supplied by a plugin, public request or application operation row.
This supports upgrading an older image without editing/binding its source tree.
"""
import configparser
import json
import re
import sys
import types
import psycopg2


def main():
    value=json.load(sys.stdin)
    keys={'action','database','site_id','release_digest','control_release','operation_id','expected_digest'}
    if not isinstance(value,dict) or set(value)!=keys or value['action'] not in {'observe','fence','enable'}:
        raise ValueError('Exact private dispatch maintenance request required')
    if not isinstance(value['database'],str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,62}',value['database']):
        raise ValueError('Exact configured database required')
    module=types.ModuleType('modular_platform.host_dispatch_lifecycle')
    module.__package__='modular_platform';sys.modules[module.__name__]=module
    exec(compile(LIFECYCLE_SOURCE,'host_dispatch_lifecycle','exec'),module.__dict__)
    scope=module.LifecycleScope(value['site_id'],value['release_digest'],value['control_release'])
    config=configparser.ConfigParser();assert config.read('/run/secrets/odoo_config')
    options=config['options']
    connection=psycopg2.connect(host=options['db_host'],port=options['db_port'],user=options['db_user'],password=options['db_password'],dbname=value['database'],connect_timeout=5)
    try:
        connection.set_session(isolation_level='REPEATABLE READ' if value['action']=='observe' else 'READ COMMITTED',readonly=value['action']=='observe')
        with connection.cursor() as cr:
            cr.execute("SET LOCAL statement_timeout='15s'; SET LOCAL lock_timeout='10s'")
            result=(module.fence(cr,scope,value['operation_id']) if value['action']=='fence' else
                module.enable(cr,scope,value['expected_digest']) if value['action']=='enable' else module.observe(cr,scope))
        connection.commit()
        print(json.dumps(dict(action=value['action'],result=result)))
    finally:connection.close()


if __name__=='__main__':main()
