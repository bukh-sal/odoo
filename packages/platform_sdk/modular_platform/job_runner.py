"""Inventoried native job process: validate pins before importing Odoo.

This host backend process has the application's scoped DB connection. It is
separate from the reference external stats worker, which never receives it.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
from uuid import uuid4


def validate_startup():
    import psycopg2
    root=Path('/opt/modular');raw=(root/'distribution-inventory.json').read_bytes()
    database=os.environ.get('MP_EXPECTED_DATABASE','');pin=os.environ.get('MP_EXPECTED_INVENTORY_DIGEST','')
    if not database or not re.fullmatch(r'sha256:[0-9a-f]{64}',pin) or 'sha256:'+hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('Independent job database and inventory pins required')
    inventory=json.loads(raw)
    for name in ['packages/platform_sdk/modular_platform/job_runner.py','packages/platform_sdk/modular_platform/worker_start.py']:
        path=root/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=inventory['files'][name]:
            raise ValueError('Job bootstrap source differs from inventory')
    configuration=configparser.ConfigParser();configuration.read('/run/secrets/odoo_config');options=configuration['options']
    bootstrap=runpy.run_path(str(root/'packages/platform_sdk/modular_platform/worker_start.py'),run_name='verified_job_bootstrap')
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
    connection.set_session(readonly=True,autocommit=True)
    try:bootstrap['validate'](str(root),options,connection,database,pin)
    finally:connection.close()
    return database


def emit(**fields):
    print(json.dumps(fields,sort_keys=True),flush=True)


def run_once(registry,owner):
    from odoo import api
    from odoo.service.model import retrying
    from odoo.addons.mp_core import job_dispatch as jobs
    from modular_platform import durable
    # Superuser environment is restricted to scheduler/config metadata here.
    # jobs reconstructs the actual mapped user before any business operation.
    with registry.cursor() as cr:
        metadata=api.Environment(cr,1,{})
        try:invocation=retrying(lambda:jobs.prepare_one(metadata,owner),metadata)
        except durable.DispatchPaused:
            cr.rollback();return dict(state='paused')
    if invocation is None:return dict(state='idle')
    if isinstance(invocation,dict):return invocation
    try:
        computed=jobs.compute(invocation)
    except Exception:
        with registry.cursor() as cr:
            metadata=api.Environment(cr,1,{})
            try:state=retrying(lambda:durable.fail(cr,invocation.claim,'INTERNAL_ERROR',retryable=False),metadata)
            except (durable.ClaimLost,durable.DispatchPaused):
                cr.rollback();return dict(job_id=invocation.claim.job_id,state='claim_lost')
        return dict(job_id=invocation.claim.job_id,state=state,error_code='INTERNAL_ERROR')
    with registry.cursor() as cr:
        metadata=api.Environment(cr,1,{})
        try:result=retrying(lambda:jobs.finish_one(metadata,invocation,computed),metadata)
        except (durable.ClaimLost,durable.DispatchPaused):
            cr.rollback();return dict(job_id=invocation.claim.job_id,state='claim_lost')
    if isinstance(result,dict) and result.get('job_id')==invocation.claim.job_id:return result
    return dict(job_id=invocation.claim.job_id,state='completed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--poll-seconds',type=float,default=1.0);args=parser.parse_args()
    if not 0.1<=args.poll_seconds<=30:raise ValueError('Bounded job poll interval required')
    database=validate_startup()
    # Native/plugin imports occur only after immutable code/config/DB guards.
    # Odoo19 uses a namespace package. Registry imports its official core
    # initialization; bare ``import odoo`` supplies neither tools nor modules.
    from odoo.modules.registry import Registry
    from odoo.tools import config
    config.parse_config(['-c','/run/secrets/odoo_config','--no-http','--workers=0','--max-cron-threads=0'])
    registry=Registry(database);owner=str(uuid4())
    while True:
        try:result=run_once(registry,owner)
        except Exception:
            # No exception representation, stack arguments, SQL or input text.
            emit(state='error',error_code='INTERNAL_ERROR')
            if args.once:return 1
            time.sleep(args.poll_seconds);continue
        emit(**result)
        if args.once:return 0
        if result['state'] in {'idle','paused','claim_lost'}:time.sleep(args.poll_seconds)


if __name__=='__main__':sys.exit(main())
