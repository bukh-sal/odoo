"""Supervision for a guarded native lane. One process slot per workspace/pool."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import os
import selectors
import signal
import subprocess
import sys
from threading import Event, Lock, Thread
import time
from uuid import uuid4

from modular_platform import durable
from modular_platform import job_fairness
from modular_platform import job_health


LEASE_SECONDS = 6
_reporter = ContextVar('modular_job_progress', default=None)


def report_progress(percent):
    """Report monotonic progress from managed detached compute, without ORM access."""
    durable._bounded(percent, 0, 99)
    reporter = _reporter.get()
    if reporter is not None:
        reporter(percent)


def supervise(args, *, module='modular_platform.job_runner'):
    """Separate process enforces the hard deadline even if Python is stuck in C."""
    from modular_platform.job_runner import emit
    reading, writing = os.pipe()
    process = None
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
        if process is not None and process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        process = subprocess.Popen([sys.executable,'-m',module,
            *(['--pool',args.pool] if module=='modular_platform.job_runner' else []),'--poll-seconds',str(args.poll_seconds),
            '--_watchdog-fd',str(writing)], pass_fds=(writing,))
    finally:
        os.close(writing)
    if stopping:stop()
    deadline = time.monotonic()+120
    data = b''
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(reading,selectors.EVENT_READ)
            while process.poll() is None:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    emit(event='watchdog_timeout',pool=args.pool,state='error',error_code='DEADLINE_EXCEEDED')
                    process.kill()
                    process.wait()
                    return 124
                if not selector.select(min(.2,remaining)):
                    continue
                chunk = os.read(reading,1024)
                if not chunk:
                    return process.wait(timeout=5)
                data += chunk
                while b'\n' in data:
                    line,data = data.split(b'\n',1)
                    # Child sends a monotonic absolute deadline on the same host.
                    deadline = int(line)/1000
    finally:
        os.close(reading)
        if process.poll() is None:
            process.kill()
            process.wait()
    return process.returncode


@contextmanager
def workspace_slot(registry, site, pool, workspace):
    """Hold a dedicated DB session advisory lock through the entire attempt."""
    key = int.from_bytes(hashlib.sha256(f'mp-job:{site}:{pool}:{workspace}'.encode()).digest()[:8],
                         'big',signed=True)
    with registry.cursor() as cr:
        cr.execute('SELECT pg_try_advisory_lock(%s)',[key])
        locked, = cr.fetchone()
        # Session lock survives rollback; do not keep a transaction open.
        cr.rollback()
        try:
            yield locked
        finally:
            if locked:
                try:
                    cr.execute('SELECT pg_advisory_unlock(%s)',[key])
                    if not cr.fetchone()[0]:
                        raise RuntimeError('Worker workspace slot lost')
                finally:
                    cr.rollback()


def child(args):
    from modular_platform.job_runner import emit, load_registry, run_once, validate_startup
    database = validate_startup(managed=True)
    registry = load_registry(database)
    from odoo import api
    from odoo.addons.mp_core import job_dispatch as jobs
    from odoo.addons.mp_identity.release import current_release
    from odoo.service.model import retrying

    stop = Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    owner = str(uuid4())
    health_lock = Lock()
    with registry.cursor() as cr:
        initial_release = current_release(api.Environment(cr,1,{}))

    def health(state):
        with health_lock:
            job_health.publish(database=database, site_id=initial_release['site_id'],
                release_digest=initial_release['release_digest'],
                inventory_digest=os.environ['MP_EXPECTED_INVENTORY_DIGEST'], pool=args.pool,
                state='draining' if stop.is_set() else state)

    health('starting')
    emit(event='worker_ready',pool=args.pool,state='running')

    def watchdog(seconds):
        os.write(args._watchdog_fd,f'{int((time.monotonic()+seconds)*1000)}\n'.encode())

    @contextmanager
    def attempt(invocation):
        budget = (invocation.claim.budget_until-datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()
        watchdog(max(0,budget))
        done = Event()
        progress_lock = Lock()
        progress = 0
        started = time.monotonic()
        health('running')
        emit(event='claimed',pool=args.pool,job_id=invocation.claim.job_id,
             generation=invocation.claim.generation,start_delay_ms=invocation.claim.ready_ms,
             handler=invocation.handler,version=invocation.version,
             workspace=invocation.context['workspace_id'],at=datetime.now(timezone.utc).isoformat(),
             preparation_upper_bound_ms=invocation.preparation_ms)

        def report(value):
            nonlocal progress
            with progress_lock:
                progress = max(progress,value)

        def renew():
            while not done.wait(LEASE_SECONDS/3):
                try:
                    with registry.cursor() as cr:
                        metadata = api.Environment(cr,1,{})
                        with progress_lock:
                            value = progress
                        retrying(lambda:durable.heartbeat(cr,invocation.claim,
                            lease_seconds=LEASE_SECONDS,progress=value),metadata)
                    emit(event='heartbeat',pool=args.pool,job_id=invocation.claim.job_id,progress=value)
                    health('running')
                except (durable.ClaimLost,durable.DispatchPaused):
                    health('paused')
                    return
                except Exception:
                    health('error')
                    emit(event='heartbeat_error',pool=args.pool,error_code='INTERNAL_ERROR')
                    return

        thread = Thread(target=renew,daemon=True)
        token = _reporter.set(report)
        thread.start()
        try:
            yield
        finally:
            _reporter.reset(token)
            done.set()
            thread.join(timeout=1)
            watchdog(60)
            elapsed=round((time.monotonic()-started)*1000)
            emit(event='attempt_end',pool=args.pool,job_id=invocation.claim.job_id,
                 generation=invocation.claim.generation,handler=invocation.handler,version=invocation.version,
                 at=datetime.now(timezone.utc).isoformat(),duration_ms=elapsed,
                 worker_duration_ms=elapsed+invocation.preparation_ms)

    while not stop.is_set():
        watchdog(60)
        claimed = False
        try:
            routes = jobs.routes_for(args.pool)
            with registry.cursor() as cr:
                release = current_release(api.Environment(cr,1,{}))
                if release != initial_release:
                    raise durable.DispatchPaused('Managed worker release changed')
                durable.control(cr,release['site_id'],release['release_digest'])
                ticket=job_fairness.read(cr,release['site_id'],release['release_digest'],args.pool)
                workspaces = durable.ready_workspaces(cr,release['site_id'],release['release_digest'],routes,
                    after=ticket.after) if routes else []
                cr.rollback()
            health('idle')
            if routes:
                for workspace in workspaces:
                    if stop.is_set():break
                    with workspace_slot(registry,release['site_id'],args.pool,workspace) as locked:
                        if not locked or stop.is_set():continue
                        if not job_fairness.reserve(registry,ticket,workspace):
                            # Another lane advanced the ring. Discard this
                            # candidate list and observe a fresh ticket.
                            break
                        result = run_once(registry,owner,pool=args.pool,workspace_id=workspace,
                                          lease_seconds=LEASE_SECONDS,attempt=attempt)
                    if result['state'] not in {'idle','paused'}:
                        emit(event='outcome',pool=args.pool,**result)
                        claimed = True
                        break
        except durable.DispatchPaused:
            health('paused')
        except Exception:
            health('error')
            emit(event='worker_error',pool=args.pool,state='error',error_code='INTERNAL_ERROR')
        if not claimed:
            stop.wait(args.poll_seconds)
    health('stopped')
    emit(event='drained',pool=args.pool,state='stopped')
    return 0
