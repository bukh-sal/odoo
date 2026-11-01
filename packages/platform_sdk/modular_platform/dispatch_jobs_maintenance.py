"""Fixed host-owned native job reconciliation child, including old-image restore.

The host prepends the single reviewed RECONCILE_SOURCE function from its source
tree. Inputs never carry Python, model names or handlers. This does not patch a
running application or change files in the retained immutable image.
"""
import ast
import json
import os
import re
import sys
from modular_platform.plans import data_digest


def main():
    data=json.load(sys.stdin)
    keys={'action','database','site_id','deployment_id','previous_release','release_digest','inventory_digest','operation_id'}
    if not isinstance(data,dict) or set(data)!=keys or data['action'] not in {'preview','reconcile'}:
        raise ValueError('Exact independent job reconciliation request required')
    # The existing inventoried bootstrap validates all executable source, native
    # registration, configuration and database pins before any native imports.
    from modular_platform.job_runner import validate_startup
    os.environ['MP_EXPECTED_DATABASE']=data['database'];os.environ['MP_EXPECTED_INVENTORY_DIGEST']=data['inventory_digest']
    if validate_startup()!=data['database']:raise ValueError('Job reconciliation database mismatch')
    from odoo.modules.registry import Registry
    from odoo.tools import config
    from odoo import api
    config.parse_config(['-c','/run/secrets/odoo_config','--no-http','--workers=0','--max-cron-threads=0'])
    from odoo.addons.mp_core import job_dispatch as runtime
    if any(not callable(getattr(runtime,name,None)) for name in ['_environment','_authorize','_validate','_safe_code']):
        raise ValueError('Unsupported retained native job adapter')
    tree=ast.parse(RECONCILE_SOURCE)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!='reconcile_release':
        raise ValueError('Fixed host reconciliation function required')
    namespace={**vars(runtime),'re':re,'data_digest':data_digest}
    exec(compile(tree,'host_job_reconciliation','exec'),namespace)
    with Registry(data['database']).cursor() as cr:
        expected={'mp.site_id':data['site_id'],'mp.deployment_id':data['deployment_id'],
            'mp.release_digest':data['release_digest'],'mp.active_inventory_digest':data['inventory_digest']}
        cr.execute('SELECT key,value FROM ir_config_parameter WHERE key=ANY(%s)',[list(expected)])
        if dict(cr.fetchall())!=expected:raise ValueError('Native reconciliation target changed')
        result=namespace['reconcile_release'](api.Environment(cr,1,{}),previous_release=data['previous_release'],target_release=data['release_digest'])
        if data['action']=='preview':cr.rollback()
        else:cr.commit()
    print(json.dumps(dict(action=data['action'],mutation_committed=data['action']=='reconcile',result=result)))


if __name__=='__main__':main()
