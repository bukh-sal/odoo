"""Guarded host-side job observation and explicit effect reconciliation."""
import argparse
import re

from modular_platform import durable
from modular_platform.dispatch_lifecycle import LifecycleScope, history_pressure
from modular_platform.job_runner import emit,load_registry,validate_startup
from modular_platform.plans import data_digest


ACTIONS = ('retry','confirm-delivered','confirm-absent')


def queue_metrics(cr,site,release,routes):
    cr.execute("""SELECT count(*) FILTER (WHERE state IN ('pending','retry')),
        count(*) FILTER (WHERE state IN ('pending','retry') AND available_at<=now_utc AND deadline_at>now_utc),
        COALESCE(round(max(extract(epoch FROM now_utc-available_at)*1000)
            FILTER (WHERE state IN ('pending','retry') AND available_at<=now_utc AND deadline_at>now_utc)),0),
        count(*) FILTER (WHERE state='running'),
        count(*) FILTER (WHERE state='running' AND lease_until<=now_utc),
        count(*) FILTER (WHERE state='retry'), count(*) FILTER (WHERE state='dead_letter'),
        count(*) FILTER (WHERE state='outcome_unknown')
        FROM mp_job CROSS JOIN (SELECT timezone('UTC',statement_timestamp()) AS now_utc) stamp
        WHERE site_id=%s AND (release_digest=%s OR state='outcome_unknown')
          AND handler||':'||handler_version=ANY(%s)""", [site,release,[f'{n}:{v}' for n,v in routes]])
    values = [int(value) for value in cr.fetchone()]
    return dict(zip(('queued','ready','oldest_ready_ms','running','expired_leases','retry',
                     'dead_letter','outcome_unknown'), values, strict=True))


def decision(cr,site,release,job,action,evidence):
    durable._uuid(job)
    if action=='retry':
        durable.control(cr,site,release)
    cr.execute("""SELECT to_jsonb(j) FROM mp_job j WHERE site_id=%s AND public_id=%s
        AND payload->>'schema_version'='2' FOR UPDATE""",[site,job])
    found = cr.fetchone()
    if not found:
        raise durable.QueueError('Scheduled job unavailable in this deployment')
    row = found[0]
    if action=='retry':
        if (row['release_digest']!=release or row['state']!='dead_letter' or row['effect_mode']!='idempotent'
                or row['effect_started'] or row['cancel_requested'] or row['attempts']>=16):
            raise durable.QueueError('Only a current replay-safe failed job can be retried')
        cr.execute("SELECT %s::timestamp>timezone('UTC',clock_timestamp())",[row['deadline_at']])
        if not cr.fetchone()[0]:
            raise durable.QueueError('A retry cannot extend the original job expiry')
    elif row['state']!='outcome_unknown' or not row['effect_started'] or row['effect_mode']!='reconcile':
        raise durable.QueueError('A recorded uncertain effect is required')
    elif not evidence or not re.fullmatch(r'sha256:[0-9a-f]{64}',evidence):
        raise durable.QueueError('Independently reviewed effect evidence digest required')
    observed = {key:row[key] for key in ('public_id','release_digest','state','attempts','error_code',
                                         'claim_generation','effect_started')}
    review = dict(site_id=site,release=release,action=action,job=observed,evidence=evidence)
    return row,review,data_digest(review)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['metrics','history','review','apply'])
    parser.add_argument('--job')
    parser.add_argument('--action',choices=ACTIONS)
    parser.add_argument('--evidence')
    parser.add_argument('--approval')
    args=parser.parse_args()
    if args.command in {'review','apply'} and (not args.job or not args.action):
        parser.error('Explicit job and action required')
    if args.command=='apply' and not args.approval:
        parser.error('Exact reviewed decision digest required')
    db=validate_startup(managed=True,admin=True)
    registry=load_registry(db)
    from odoo import api
    from odoo.addons.mp_core import job_dispatch
    from odoo.addons.mp_identity.release import current_release
    with registry.cursor() as cr:
        release=current_release(api.Environment(cr,1,{}))
        site,digest=release['site_id'],release['release_digest']
        if args.command=='history':
            report=history_pressure(cr,LifecycleScope(site,digest))
            emit(event='job_history',**report)
            cr.rollback()
            return
        if args.command=='metrics':
            emit(event='job_metrics',pools={pool:queue_metrics(cr,site,digest,job_dispatch.routes_for(pool))
                                           for pool in ('urgent','bulk')})
            cr.rollback()
            return
        row,review,approval=decision(cr,site,digest,args.job,args.action,args.evidence)
        if args.command=='apply':
            if args.approval!=approval:
                raise durable.QueueError('Reviewed job decision is stale')
            if args.action=='retry':
                job_dispatch._authorized_job(api.Environment(cr,1,{}),row)
                cr.execute("""UPDATE mp_job SET state='retry',max_attempts=GREATEST(max_attempts,attempts+1),
                    available_at=timezone('UTC',clock_timestamp()),finished_at=NULL,error_code=NULL WHERE id=%s""",[row['id']])
            else:
                delivered=args.action=='confirm-delivered'
                cr.execute("""UPDATE mp_job SET state=%s,progress=%s,error_code=%s,
                    finished_at=timezone('UTC',clock_timestamp()),lease_owner=NULL,lease_until=NULL WHERE id=%s""",
                    ['completed' if delivered else 'dead_letter',100 if delivered else row['progress'],
                     None if delivered else 'CANCELLED',row['id']])
            cr.commit()
        else:
            cr.rollback()
        emit(event='job_control',review=review,approval=approval,applied=args.command=='apply')


if __name__=='__main__':
    main()
