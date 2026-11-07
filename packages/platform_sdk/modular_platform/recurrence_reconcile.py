"""Fixed independently selected child: reauthorize schedules while dispatch is closed."""
import json
import os
import sys

from modular_platform.job_runner import validate_startup,load_registry


def main():
    value=json.load(sys.stdin)
    if not isinstance(value,dict) or set(value)!={'database','site_id','inventory_digest','release_digest','previous_release'}:
        raise ValueError('Exact private recurring reconciliation request required')
    os.environ['MP_EXPECTED_DATABASE']=value['database']
    os.environ['MP_EXPECTED_INVENTORY_DIGEST']=value['inventory_digest']
    if validate_startup()!=value['database']:raise ValueError('Recurring reconciliation database differs')
    registry=load_registry(value['database'])
    from odoo import api
    from odoo.addons.mp_core import recurrence_dispatch
    with registry.cursor() as cr:
        cr.execute("SELECT site_id,release_digest,state FROM mp_dispatch_control FOR UPDATE")
        if cr.fetchall()!=[(value['site_id'],value['release_digest'],'paused')]:
            raise ValueError('Closed current recurring dispatch required')
        states=recurrence_dispatch.reconcile_release(api.Environment(cr,1,{}),
            previous_release=value['previous_release'],target_release=value['release_digest'])
        cr.commit()
    print(json.dumps(dict(event='recurrence_reconciled',release_digest=value['release_digest'],states=states,dispatch_enabled=False)))


if __name__=='__main__':main()
