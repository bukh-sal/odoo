"""Fixed pinned native producer role. It enqueues jobs and never runs compute."""
import argparse
import os
import signal
from threading import Event
import time

from modular_platform import durable,job_health
from modular_platform.job_runner import emit,load_registry,validate_startup


def child(args):
    database=validate_startup(managed=True)
    registry=load_registry(database)
    from odoo import api
    from odoo.service.model import retrying
    from odoo.addons.mp_identity.release import current_release
    from odoo.addons.mp_core import recurrence_dispatch
    stop=Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    with registry.cursor() as cr:initial=current_release(api.Environment(cr,1,{}))
    def health(state):
        job_health.publish(database=database,site_id=initial['site_id'],release_digest=initial['release_digest'],
            inventory_digest=os.environ['MP_EXPECTED_INVENTORY_DIGEST'],pool='producer',state='draining' if stop.is_set() else state)
    def watchdog(seconds):os.write(args._watchdog_fd,(str(int((time.monotonic()+seconds)*1000))+'\n').encode())
    def current(cr):
        env=api.Environment(cr,1,{})
        if current_release(env)!=initial:raise durable.DispatchPaused('Recurring producer release changed')
        durable.control(cr,initial['site_id'],initial['release_digest'])
        return env
    health('starting')
    while not stop.is_set():
        watchdog(60)
        try:
            with registry.cursor() as cr:
                cr.execute("SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='2s'")
                identities=recurrence_dispatch.due(current(cr))
                cr.rollback()
            health('idle')
            for ident in identities:
                if stop.is_set():break
                watchdog(30)
                with registry.cursor() as cr:
                    env=current(cr)
                    def tick():
                        cr.execute("SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='2s'")
                        return recurrence_dispatch.tick(env,ident)
                    result=retrying(tick,env)
                health('running')
                emit(event='recurrence_tick',pool='producer',**result)
        except durable.DispatchPaused:
            health('paused')
        except Exception:
            health('error')
            emit(event='recurrence_error',state='error',error_code='INTERNAL_ERROR')
        stop.wait(args.poll_seconds)
    health('stopped')
    emit(event='recurrence_drained',state='stopped')
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poll-seconds',type=float,default=.25)
    parser.add_argument('--_watchdog-fd',type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not .1<=args.poll_seconds<=5:raise ValueError('Bounded recurring producer polling required')
    if args._watchdog_fd is None:
        validate_startup(managed=True)
        from modular_platform.job_supervisor import supervise
        args.pool='producer'
        return supervise(args,module='modular_platform.recurrence_runner')
    return child(args)


if __name__=='__main__':raise SystemExit(main())
