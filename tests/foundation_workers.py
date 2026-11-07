"""Reviewed background lanes and useful peer work during independent recovery."""
import argparse
from datetime import datetime, timezone
import json
import time

from foundation_release import FoundationSite, StressClient, load, write
from foundation_lifecycle import sql
from foundation_jobs import shell
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest


ENQUEUE = '''
from datetime import datetime,timedelta,timezone
import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import job_dispatch
from modular_platform.durable import JobSchedule
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),
                         FIXTURE['workspaces']['A']['public_id'])
now=datetime.now(timezone.utc);jobs=[]
for index in range(COUNT):
    jobs.append(job_dispatch.enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs',
        'org.example.background:report',dict(first=1,last=500),PREFIX+str(index),version=2,
        schedule=JobSchedule(now,now+timedelta(minutes=10),20)))
env.cr.commit()
print('CF_PEER_JOBS='+json.dumps(jobs))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['start', 'peer_work', 'verify', 'urgent', 'drain'])
    parser.add_argument('site', choices=['aurora', 'maintenance'])
    args = parser.parse_args()
    args.run = 'cf-01'
    site = FoundationSite(args)
    target = load(site.private / 'target.json')
    op = JobOperator(OperatorStore(site.private / 'control'), site.private / 'target.json')
    path = site.local / 'workers.json'
    if args.phase == 'start':
        assert not path.exists()
        review = op.run('profile-review', urgent_lanes=1, bulk_lanes=1, shutdown_seconds=5)
        record = dict(phase='reviewed', approval=review['approval'], target_digest=data_digest(target))
        write(path, record)
        result = op.run('profile-apply', approval=review['approval'])
        assert result['state'] == 'ready'
        record.update(phase='ready', profile=result)
        write(path, record)
        print(json.dumps(dict(result='ready', site=args.site, urgent=1, bulk=1)))
    elif args.phase == 'peer_work':
        assert args.site == 'maintenance'
        other = site.local.parent / 'aurora'
        fault = load(other / 'fault.json')
        assert fault['phase'] == 'recovery_required' and fault['failed_app_stopped']
        assert OperatorStore(other / 'operator/control').status(fault['operation'])['state'] == 'recovery_required'
        output = site.local / 'peer-work.json'
        assert not output.exists()
        code = f"FIXTURE={load(site.local / 'fixtures.json')!r}\nCOUNT=16\nPREFIX='cf-peer-recovery-'\n" + ENQUEUE
        started = datetime.now(timezone.utc).isoformat()
        raw = shell(site, 'cf-peer-recovery-work', code)
        jobs, = [json.loads(line.split('=', 1)[1]) for line in raw.splitlines() if line.startswith('CF_PEER_JOBS=')]
        write(output, dict(phase='queued', jobs=jobs, started_utc=started, aurora_fault=fault['operation'],
                           target_digest=data_digest(target)))
        print(json.dumps(dict(result='queued', jobs=len(jobs), peer_app_down=True)))
    elif args.phase == 'verify':
        output = site.local / 'peer-work.json'
        record = load(output)
        assert record['phase'] == 'queued' and data_digest(target) == record['target_digest']
        ids = ','.join("'" + ident + "'" for ident in record['jobs'])
        until = time.monotonic() + 180
        while True:
            rows = json.loads(sql(target, f"SELECT jsonb_agg(jsonb_build_object('id',public_id,'state',state,'attempts',attempts,'result',result,'finished_at',finished_at)) FROM mp_job WHERE public_id IN ({ids});"))
            if all(row['state'] == 'completed' for row in rows):
                break
            assert time.monotonic() < until, rows
            time.sleep(.5)
        assert len(rows) == 16 and all(row['attempts'] == 1 and row['result']['count'] == 2 and row['result']['points'] == 10 for row in rows)
        status = op.run('status')
        assert status['state'] == 'ready'
        record.update(phase='verified', rows=rows, peer_config_unchanged=True,
                      profile_ready=True, checked_utc=datetime.now(timezone.utc).isoformat())
        write(output, record)
        print(json.dumps(dict(result='passed', completed_once=16, exact_count=2, exact_points=10)))
    elif args.phase == 'urgent':
        output = site.local / 'urgent-work.json'
        assert not output.exists()
        fixture = load(site.local / 'fixtures.json')
        code = f'FIXTURE={fixture!r}\n' + '''
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
import json
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']])
principal=env.cr.fetchone()[0]
task=actor['mp.background.task'].create(dict(name='Current release urgent reference',points=0,
    assignee_id=principal,due_at=(datetime.now(timezone.utc)+timedelta(seconds=1)).replace(tzinfo=None)))
job=task._queue_current();env.cr.commit()
print('CF_URGENT='+json.dumps(dict(task=task.id,job=job)))
'''
        raw = shell(site, 'cf-current-urgent', code)
        data, = [json.loads(line.split('=', 1)[1]) for line in raw.splitlines() if line.startswith('CF_URGENT=')]
        write(output, dict(phase='queued', **data))
        deadline = time.monotonic() + 50
        while sql(target, f"SELECT state FROM mp_job WHERE public_id='{data['job']}';") != 'completed':
            assert time.monotonic() < deadline
            time.sleep(.5)
        assert sql(target, f"SELECT count(*) FROM mp_background_notification WHERE task_id={data['task']};") == '1'
        record = dict(phase='verified', **data, notification_once=True, image=target['image_id'])
        write(output, record)
        print(json.dumps(dict(result='passed', urgent_notification_once=True)))
    else:
        result = op.run('drain')
        assert result['state'] == 'paused'
        print(json.dumps(dict(result='drained', site=args.site)))


if __name__ == '__main__':
    main()
