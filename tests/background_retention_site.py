"""Exercise native dispatch and archival on the reviewed disposable BX image."""

import json
from types import SimpleNamespace

from background_site import BackgroundSite, load, write


PROBE = """
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from modular_platform import durable
from modular_platform.dispatch_lifecycle import JOB_IDENTITY, LifecycleScope, observe
from modular_platform.job_runner import run_once
from odoo import api
from odoo.addons.mp_core import job_dispatch
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_identity.scopes import scoped_environment

assert env.cr.dbname == FIXTURE_DB and FIXTURE_DB.startswith(('mp_disposable_r0_r1_release_', 'mp_disposable_r0_r1_restore_'))
registry = env.registry
release = current_release(env)
site = release['site_id']
digest = release['release_digest']
assert site == FIXTURE['site_id']
run_at = datetime.now(timezone.utc)
schedule = durable.JobSchedule(run_at, run_at + timedelta(seconds=60), 20)
cutoff = run_at - timedelta(days=1)


def submit(cursor, workspace='A', user='alice', last=1):
    actor = scoped_environment(api.Environment(cursor, FIXTURE['users'][user]['id'], {}),
                               FIXTURE['workspaces'][workspace]['public_id'])
    tasks = actor['mp.background.task']
    return job_dispatch.enqueue_scheduled(
        tasks._job_env(), 'jobs', 'org.example.background:report',
        {'first': 1, 'last': last}, 'bx01-archive-native', version=2, schedule=schedule,
    )


with registry.cursor() as cr:
    job = submit(cr)
    assert submit(cr) == job
    cr.commit()
for attempt in range(3):
    run_once(registry, str(uuid4()), pool='bulk')
    with registry.cursor() as cr:
        cr.execute('SELECT state FROM mp_job WHERE public_id=%s', [job])
        if cr.fetchone() == ('completed',):
            break
else:
    raise AssertionError('The retained fixture job did not complete')
with registry.cursor() as cr:
    cr.execute("SELECT state FROM mp_job WHERE public_id=%s", [job])
    assert cr.fetchone() == ('completed',)
    # Simulate elapsed retention time for the exact synthetic row.
    cr.execute('UPDATE mp_job SET deadline_at=%s,finished_at=%s WHERE public_id=%s',
               [cutoff, cutoff, job])
    assert durable.archive_terminal_jobs(cr, site, digest, cutoff=cutoff, limit=1) == [job]
    cr.commit()
with registry.cursor() as cr:
    assert submit(cr) == job
    try:
        submit(cr, last=2)
    except durable.QueueError as error:
        assert 'deduplication' in str(error)
    else:
        raise AssertionError('Archived idempotency conflict must be refused')
    other = submit(cr, workspace='B', user='bob')
    assert other != job
    cr.rollback()
with registry.cursor() as cr:
    cr.execute('SELECT job_public_id,terminal_state FROM mp_job_identity WHERE job_public_id=%s', [job])
    assert cr.fetchone() == (job, 'completed')
    cr.execute('SELECT count(*) FROM mp_job WHERE public_id=%s', [job])
    assert cr.fetchone() == (0,)
    snapshot = observe(cr, LifecycleScope(site, digest))
    assert snapshot['tables'][JOB_IDENTITY]['rows'] >= 1
print('MP_BX_RESULT=' + json.dumps({
    'native_handler_completed': True, 'archived_job_returned_original_id': True,
    'changed_input_refused': True, 'separate_workspace_received_distinct_job': True,
    'identity_in_lifecycle_snapshot': True,
}))
"""


def run():
    site = BackgroundSite(SimpleNamespace(run='bx-01-retention-01'))
    state = site.state()
    assert state['phase'] == 'bg02_probed'
    target = load(site.private / 'target.json')
    assert target['project'] == state['project']
    assert target['sites'] == [{'site_id': state['site_id'], 'database': state['database']}]
    source = 'FIXTURE_DB = ' + repr(state['database']) + '\nFIXTURE = ' + repr(load(site.local / 'fixtures.json'))
    raw = site.native(state, 'bx01-native-retention', [], source + '\n' + PROBE)
    record, = [json.loads(row.split('=', 1)[1]) for row in raw.decode().splitlines() if row.startswith('MP_BX_RESULT=')]
    write(site.local / 'retention-native-result.json', dict(image=state['image_id'], **record))
    site.phase(state, 'bx01_retention_probed')
    print(json.dumps(record))


if __name__ == '__main__':
    run()
