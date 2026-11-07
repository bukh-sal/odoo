"""Inventoried native job process: validate pins before importing Odoo.

This host backend process has the application's scoped DB connection. It is
separate from the reference external stats worker, which never receives it.
"""
import argparse
import configparser
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
from uuid import uuid4


def validate_startup(*,managed=False,admin=False):
    import psycopg2
    root=Path('/opt/modular');raw=(root/'distribution-inventory.json').read_bytes()
    database=os.environ.get('MP_EXPECTED_DATABASE','');pin=os.environ.get('MP_EXPECTED_INVENTORY_DIGEST','')
    if not database or not re.fullmatch(r'sha256:[0-9a-f]{64}',pin) or 'sha256:'+hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('Independent job database and inventory pins required')
    inventory=json.loads(raw)
    files=['job_runner.py','worker_start.py']
    if managed:files.append('job_supervisor.py')
    if admin:files.append('job_admin.py')
    for filename in files:
        name='packages/platform_sdk/modular_platform/'+filename
        path=root/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=inventory['files'][name]:
            raise ValueError('Job bootstrap source differs from inventory')
    configuration=configparser.ConfigParser();configuration.read('/run/secrets/odoo_config');options=configuration['options']
    bootstrap=runpy.run_path(str(root/'packages/platform_sdk/modular_platform/worker_start.py'),run_name='verified_job_bootstrap')
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
    connection.set_session(readonly=True,autocommit=True)
    try:bootstrap['validate'](str(root),options,connection,database,pin)
    finally:connection.close()
    site=os.environ.get('MP_EXPECTED_SITE_ID')
    release=os.environ.get('MP_EXPECTED_RELEASE_DIGEST')
    if site is not None or release is not None:
        from modular_platform import durable
        durable._uuid(site)
        if not isinstance(release,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',release):
            raise ValueError('Exact managed worker site and release required')
        connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=database,connect_timeout=5)
        try:
            with connection.cursor() as cr:
                cr.execute("SELECT key,value FROM ir_config_parameter WHERE key IN ('mp.site_id','mp.release_digest')")
                if dict(cr.fetchall())!={'mp.site_id':site,'mp.release_digest':release}:
                    raise ValueError('Managed worker site or release pin changed')
        finally:connection.close()
    return database


def emit(**fields):
    print(json.dumps(fields,sort_keys=True),flush=True)


@contextmanager
def _claim_guard(cr,pool,workspace):
    """Own a fresh preparation cursor; compute uses a different session slot.

    Roll back the lock-acquisition snapshot before observing jobs. Otherwise a
    repeatable-read snapshot taken just before the previous claimant commits
    can miss its running row. Keep this guard until preparation has committed.
    """
    if pool=='legacy' or workspace is None:
        yield True;return
    from modular_platform import durable
    cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'")
    found=cr.fetchone()
    if not found:raise durable.QueueError('Native site required before pooled claim')
    key=durable.claim_guard_key(found[0],pool,workspace)
    cr.rollback()
    cr.execute('SELECT pg_try_advisory_lock(%s)',[key]);locked,=cr.fetchone()
    cr.rollback()
    try:yield locked
    finally:
        if locked:
            try:cr.execute('SELECT pg_advisory_unlock(%s)',[key])
            finally:cr.rollback()


def run_once(registry,owner,*,pool='legacy',workspace_id=None,lease_seconds=30,attempt=None):
    from dataclasses import replace
    import time
    from odoo import api
    from odoo.service.model import retrying
    from odoo.addons.mp_core import job_dispatch as jobs
    from modular_platform import durable
    # Superuser environment is restricted to scheduler/config metadata here.
    # jobs reconstructs the actual mapped user before any business operation.
    preparing=time.monotonic()
    with registry.cursor() as cr:
        with _claim_guard(cr,pool,workspace_id) as allowed:
            if not allowed:return dict(state='idle')
            metadata=api.Environment(cr,1,{})
            try:invocation=retrying(lambda:jobs.prepare_one(metadata,owner,pool=pool,
                workspace_id=workspace_id,lease_seconds=lease_seconds),metadata)
            except durable.DispatchPaused:
                cr.rollback();return dict(state='paused')
    if invocation is None:return dict(state='idle')
    if isinstance(invocation,dict):return invocation
    # Includes claim selection, authorization, preparation and commit. This is
    # a conservative upper bound, avoiding omitted preparation in sizing data.
    invocation=replace(invocation,preparation_ms=round((time.monotonic()-preparing)*1000))
    if attempt:
        with attempt(invocation):
            return _execute(registry,invocation)
    return _execute(registry,invocation)


def _execute(registry,invocation):
    from odoo import api
    from odoo.service.model import retrying
    from odoo.addons.mp_core import job_dispatch as jobs
    from modular_platform import durable
    try:
        computed=jobs.compute(invocation)
    except Exception as error:
        code=jobs._safe_code(error)
        if code=='CANCELLED':
            # Detached authority checks report cancelled/paused/reclaimed
            # claims this way. They are not registered failures to persist.
            # Do not touch an obsolete claim or reinterpret remote rollback.
            return dict(job_id=invocation.claim.job_id,state='claim_lost')
        with registry.cursor() as cr:
            metadata=api.Environment(cr,1,{})
            try:state=retrying(lambda:durable.fail(cr,invocation.claim,code,retryable=isinstance(error,durable.RetryJob)),metadata)
            except (durable.ClaimLost,durable.DispatchPaused):
                cr.rollback();return dict(job_id=invocation.claim.job_id,state='claim_lost')
        return dict(job_id=invocation.claim.job_id,state=state,error_code=code)
    with registry.cursor() as cr:
        metadata=api.Environment(cr,1,{})
        try:result=retrying(lambda:jobs.finish_one(metadata,invocation,computed),metadata)
        except (durable.ClaimLost,durable.DispatchPaused):
            cr.rollback();return dict(job_id=invocation.claim.job_id,state='claim_lost')
    if isinstance(result,dict) and result.get('job_id')==invocation.claim.job_id:return result
    return dict(job_id=invocation.claim.job_id,state='completed')


def load_registry(database):
    # Native/plugin imports occur only after immutable code/config/DB guards.
    from odoo.modules.registry import Registry
    from odoo.tools import config
    config.parse_config(['-c','/run/secrets/odoo_config','--no-http','--workers=0','--max-cron-threads=0'])
    return Registry(database)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--poll-seconds',type=float,default=1.0)
    parser.add_argument('--pool',choices=['urgent','bulk'])
    parser.add_argument('--_watchdog-fd',type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not 0.1<=args.poll_seconds<=30:raise ValueError('Bounded job poll interval required')
    if args.pool:
        if args.once:parser.error('Managed pools run continuously')
        from modular_platform.job_supervisor import child,supervise
        return (child(args) if args._watchdog_fd is not None else supervise(args))
    if args._watchdog_fd is not None:parser.error('Watchdog requires a managed pool')
    database=validate_startup()
    registry=load_registry(database);owner=str(uuid4())
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
