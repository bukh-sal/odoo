"""Qualify reviewed job cleanup and interruption recovery on a disposable site."""

from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

from background_site import ROOT, load, write
from background_workers import Probe
from modular_platform.job_operator import _write_new


RUN = 'bx-01-archive-operator-01'


class LostResult(Exception):
    pass


def run():
    probe = Probe(RUN)
    assert probe.state['phase'] == 'bg02_probed'
    assert probe.state['database'].startswith('mp_disposable_r0_r1_release_')
    assert not probe.operator._lanes()
    command = [sys.executable, '-I', str(ROOT / 'tools/modular.py'), '--config',
               str(probe.site.private / 'trust.json'), 'jobs', '--store', str(probe.site.private / 'control'),
               '--deployment-config', str(probe.site.private / 'target.json')]

    def cli(*args, ok=True):
        proc = subprocess.run([*command, *args], cwd=ROOT, capture_output=True, timeout=120)
        if ok:
            assert proc.returncode == 0, (args[0], proc.stderr.decode())
            return json.loads(proc.stdout)
        assert proc.returncode == 2 and json.loads(proc.stderr)['error'] == 'VALIDATION_FAILED', args[0]

    cutoff = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()

    def review(limit):
        return cli('archive-review', '--cutoff', cutoff, '--limit', str(limit))

    recent = datetime.now(timezone.utc).isoformat()
    cli('archive-review', '--cutoff', recent, '--limit', '2', ok=False)
    cli('archive-review', '--cutoff', cutoff, '--limit', '101', ok=False)
    first, changed, second, last, remote, extended = [str(uuid4()) for _ in range(6)]
    jobs = [(first, 'completed', 'idempotent', 9), (changed, 'completed', 'idempotent', 9),
            (second, 'cancelled', 'idempotent', 9), (last, 'dead_letter', 'idempotent', 9),
            (remote, 'completed', 'reconcile', 9), (extended, 'completed', 'idempotent', 3)]
    values = ','.join(f"({index},'{job}','{state}','{mode}',{days})"
                      for index, (job, state, mode, days) in enumerate(jobs))
    actor = probe.fixture['users']['alice']['principal_id']
    workspace = probe.fixture['workspaces']['A']['public_id']
    probe.sql(f"""WITH seed (ordinal, job, state, effect, deadline_days) AS (VALUES {values}),
        history AS (
            SELECT * FROM seed UNION ALL
            SELECT 6+n,gen_random_uuid()::text,'completed','idempotent',1 FROM generate_series(1,100002) n)
        INSERT INTO mp_job
            (public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
             release_digest,payload,input_digest,idempotency_key,effect_mode,state,attempts,
             max_attempts,claim_generation,dispatch_generation,available_at,deadline_at,
             cancel_requested,effect_started,progress,created_at,finished_at)
        SELECT h.job,c.site_id,w.id,p.id,i.id,'org.example.background:report',2,
            c.release_digest,'{{}}'::jsonb,'sha256:'||repeat('a',64),'bx-archive-probe:'||h.ordinal,h.effect,h.state,
            1,1,1,c.generation,now()-interval '10 days',now()-h.deadline_days*interval '1 day',false,false,100,
            now()-interval '10 days',now()-CASE WHEN h.ordinal>5 THEN interval '1 day' ELSE interval '9 days' END
        FROM history h CROSS JOIN mp_dispatch_control c CROSS JOIN mp_workspace w CROSS JOIN mp_principal p
        CROSS JOIN mp_plugin_installation i WHERE p.public_id='{actor}' AND w.public_id='{workspace}'
            AND i.plugin_id='org.example.background' ORDER BY h.ordinal""")
    assert cli('history')['tables']['mp_job']['status'] == 'over_limit'

    stale = review(2)
    assert stale['review']['jobs'] == [first, changed]
    assert cli('archive-status', stale['approval'])['jobs'] == {first: 'live', changed: 'live'}
    probe.sql(f"UPDATE mp_job SET state='held' WHERE public_id='{changed}'")
    cli('archive-apply', stale['approval'], ok=False)
    status = cli('archive-status', stale['approval'])
    assert status['attempted'] and not status['result_recorded']
    assert status['jobs'] == {first: 'live', changed: 'live'}

    interrupted = review(2)
    assert interrupted['review']['jobs'] == [first, second]

    def drop_result(path, value):
        if path.name.endswith('.result.json'):
            raise LostResult('Simulated loss after the Docker child committed')
        return _write_new(path, value)

    with patch('modular_platform.job_operator._write_new', side_effect=drop_result):
        try:
            probe.operator.run('archive-apply', approval=interrupted['approval'])
        except LostResult:
            pass
        else:
            raise AssertionError('Result loss was not injected')
    status = cli('archive-status', interrupted['approval'])
    assert status['attempted'] and not status['result_recorded']
    assert status['jobs'] == {first: 'archived', second: 'archived'}
    cli('archive-apply', interrupted['approval'], ok=False)

    final = review(2)
    assert final['review']['jobs'] == [last]
    assert cli('archive-apply', final['approval'])['jobs'] == [last]
    status = cli('archive-status', final['approval'])
    assert status['attempted'] and status['result_recorded'] and status['jobs'] == {last: 'archived'}
    assert review(2)['review']['jobs'] == []
    assert probe.sql(f"SELECT count(*) FROM mp_job WHERE public_id IN ('{changed}','{remote}','{extended}')") == '3'
    assert cli('history')['tables']['mp_job']['status'] == 'over_limit'
    result = dict(image=probe.state['image_id'], over_cap_before_and_after=True, cutoff_refused=True,
                  excessive_limit_refused=True, review_read_only=True, stale_batch_rolled_back=True,
                  commit_without_result_reconciled=True, repeated_approval_refused=True, resumed_next_batch=True,
                  review_sizes=[2, 2, 1, 0], archived_jobs=3, excluded_jobs_preserved=3)
    write(probe.site.local / 'archive-operator-result.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    run()
