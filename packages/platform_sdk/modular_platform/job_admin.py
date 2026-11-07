"""Guarded host-side job observation and explicit effect reconciliation."""
import argparse
from datetime import datetime, timezone
import json
import re

from modular_platform import durable, event_retention
from modular_platform.dispatch_lifecycle import LifecycleScope, history_pressure
from modular_platform.job_runner import emit,load_registry,validate_startup
from modular_platform.plans import data_digest


ACTIONS = ('retry','confirm-delivered','confirm-absent')
ARCHIVE_COMMANDS = ('archive-review', 'archive-apply', 'archive-status')
ARCHIVE_POLICY = 'native-terminal-v1'
ARCHIVE_MINIMUM_DAYS = 7
ARCHIVE_MAX_BATCH = 100


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


def archive_decision(cr, site, release, cutoff, limit, review_id, *, kind='job', apply=False):
    durable._uuid(review_id)
    try:
        cutoff = datetime.fromisoformat(cutoff)
    except (ValueError, TypeError):
        raise durable.QueueError('Explicit timezone-aware archive cutoff required') from None
    utc = durable._archive_cutoff(cutoff)
    if kind != 'job':
        generation, rows = event_retention.candidates(cr, site, release, kind, cutoff, limit, apply=apply)
        review = dict(policy=event_retention.POLICY, minimum_days=event_retention.MINIMUM_DAYS, review_id=review_id,
                      site_id=site, release=release, dispatch_generation=generation,
                      cutoff=utc.replace(tzinfo=timezone.utc).isoformat(), limit=limit, kind=kind,
                      records=[row[1] for row in rows], selection_digest=data_digest([list(row) for row in rows]))
        return cutoff, rows, review
    durable._bounded(limit, 1, ARCHIVE_MAX_BATCH)
    generation = durable.control(cr, site, release)
    cr.execute("""SELECT %s<=timezone('UTC',statement_timestamp())-(%s*interval '1 day')""",
               [utc, ARCHIVE_MINIMUM_DAYS])
    if not cr.fetchone()[0]:
        raise durable.QueueError('Archive cutoff must preserve the minimum retention window')
    rows = durable.terminal_archive_candidates(cr, site, cutoff=cutoff, limit=limit)
    review = dict(policy=ARCHIVE_POLICY, minimum_days=ARCHIVE_MINIMUM_DAYS, review_id=review_id,
                  site_id=site, release=release, dispatch_generation=generation,
                  cutoff=utc.replace(tzinfo=timezone.utc).isoformat(), limit=limit,
                  jobs=[row[8] for row in rows],
                  selection_digest=data_digest([list(row[:-1])+[row[-1].isoformat()] for row in rows]))
    return cutoff, rows, review


def archive_status(cr, site, jobs):
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= ARCHIVE_MAX_BATCH:
        raise durable.QueueError('Explicit bounded archive status IDs required')
    for job in jobs:
        durable._uuid(job)
    if len(set(jobs)) != len(jobs):
        raise durable.QueueError('Archive status IDs must be distinct')
    cr.execute("""SELECT wanted.id, CASE
            WHEN j.id IS NOT NULL AND a.id IS NOT NULL THEN 'conflict'
            WHEN j.id IS NOT NULL THEN 'live'
            WHEN a.id IS NOT NULL THEN 'archived'
            ELSE 'missing' END
        FROM unnest(%s::text[]) WITH ORDINALITY AS wanted(id,position)
        LEFT JOIN mp_job j ON j.site_id=%s AND j.public_id=wanted.id
        LEFT JOIN mp_job_identity a ON a.site_id=%s AND a.job_public_id=wanted.id
        ORDER BY wanted.position""", [jobs, site, site])
    return dict(cr.fetchall())


def run_archive(cr, site, release, args):
    cr.execute("SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='500ms'")
    job = args.kind == 'job'
    event = 'job_archive' if job else 'event_archive'
    if args.command == 'archive-status':
        ids = json.loads(args.jobs)
        result = (dict(jobs=archive_status(cr, site, ids)) if job else
                  dict(kind=args.kind, records=event_retention.status(cr, site, args.kind, ids)))
        cr.rollback()
        emit(event=event+'_status', **result)
        return
    applied = args.command == 'archive-apply'
    cutoff, rows, review = archive_decision(cr, site, release, args.cutoff, args.limit, args.review_id,
                                            kind=args.kind, apply=applied)
    approval = data_digest(review)
    if applied:
        if not rows or args.approval != approval:
            raise durable.QueueError('Reviewed archive batch is empty or stale')
        if job:
            archived = durable.archive_terminal_jobs(cr, site, release, cutoff=cutoff, limit=args.limit, expected=rows)
            if archived != review['jobs']:
                raise durable.QueueError('Archive result differs from the reviewed batch')
        else:
            event_retention.archive(cr, site, args.kind, rows)
        cr.commit()
    else:
        cr.rollback()
    emit(event=event, review=review, approval=approval, applied=applied)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('metrics','capacity','history','review','apply','dispatch','recurrence-authority',*ARCHIVE_COMMANDS))
    parser.add_argument('--job')
    parser.add_argument('--action',choices=ACTIONS)
    parser.add_argument('--evidence')
    parser.add_argument('--approval')
    parser.add_argument('--cutoff')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--review-id')
    parser.add_argument('--jobs')
    parser.add_argument('--kind', choices=('job', *event_retention.TABLES), default='job')
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
        if args.command == 'archive-apply' and args.kind != 'job':
            cr.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        release=current_release(api.Environment(cr,1,{}))
        site,digest=release['site_id'],release['release_digest']
        if args.command=='capacity':
            from modular_platform.job_capacity import observe
            report=observe(cr,site,digest,{pool:job_dispatch.routes_for(pool) for pool in ('urgent','bulk')})
            cr.execute('SELECT state FROM mp_dispatch_control WHERE site_id=%s AND release_digest=%s',[site,digest])
            state=cr.fetchone()
            cr.rollback()
            emit(event='job_capacity',dispatch=state[0] if state else 'unavailable',**report)
            return
        if args.command=='recurrence-authority':
            from modular_platform.recurrence_authority import review
            policy=review(cr,site)
            cr.rollback()
            emit(event='recurrence_authority',policy=policy)
            return
        if args.command=='dispatch':
            durable.control(cr,site,digest)
            cr.rollback()
            emit(event='job_dispatch',site_id=site,release_digest=digest,enabled=True)
            return
        if args.command in ARCHIVE_COMMANDS:
            run_archive(cr, site, digest, args)
            return
        if args.command=='history':
            report=history_pressure(cr,LifecycleScope(site,digest))
            alerts = [dict(table=table, status=value['status'], rows_observed=value['rows_observed'],
                           count_is_lower_bound=value['count_is_lower_bound'])
                      for table, value in report['tables'].items() if value['status'] != 'below_warning']
            emit(event='job_history',alerts=alerts,**report)
            cr.rollback()
            return
        if args.command=='metrics':
            cr.execute('SELECT state,count(*) FROM mp_job_schedule WHERE site_id=%s GROUP BY state',[site])
            schedules=dict(cr.fetchall())
            emit(event='job_metrics',pools={pool:queue_metrics(cr,site,digest,job_dispatch.routes_for(pool))
                                           for pool in ('urgent','bulk')},schedules=schedules)
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
