"""Exercise the guarded history CLI on a freshly installed disposable site."""

import json
import sys
from types import SimpleNamespace

from background_site import BackgroundSite, ROOT, load, write


def run():
    site = BackgroundSite(SimpleNamespace(run='bx-01-history-01'))
    state = site.state()
    assert state['phase'] == 'background_installed'
    target = site.private / 'target.json'
    config = load(target)
    assert config['project'] == state['project']
    assert config['sites'] == [{'site_id': state['site_id'], 'database': state['database']}]
    assert state['database'].startswith('mp_disposable_r0_r1_release_')
    command = [
        sys.executable, '-I', str(ROOT / 'tools/modular.py'),
        '--config', str(site.private / 'trust.json'), 'jobs',
        '--store', str(site.private / 'control'), '--deployment-config', str(target), 'history',
    ]
    before = json.loads(site.command('history-before', command))
    assert before['event'] == 'job_history'
    assert before['tables']['mp_job']['rows_observed'] == 0
    site.sql(state, 'history-populate', """
        INSERT INTO mp_job
            (public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
             release_digest,payload,input_digest,idempotency_key,effect_mode,state,attempts,
             max_attempts,claim_generation,dispatch_generation,available_at,deadline_at,
             cancel_requested,effect_started,progress,created_at,finished_at)
        SELECT gen_random_uuid()::text,c.site_id,w.id,p.id,i.id,'org.example.background:report',2,
            c.release_digest,'{}'::jsonb,'sha256:'||repeat('a',64),'bx-history-probe:'||n,
            'idempotent','completed',1,1,1,c.generation,now(),now(),false,false,100,now(),now()
        FROM generate_series(1,100002) n
        CROSS JOIN mp_dispatch_control c
        CROSS JOIN (SELECT id FROM mp_workspace ORDER BY id LIMIT 1) w
        CROSS JOIN (SELECT id FROM mp_principal ORDER BY id LIMIT 1) p
        CROSS JOIN (SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.background' LIMIT 1) i;
    """)
    after = json.loads(site.command('history-after', command))
    assert after['event'] == 'job_history'
    assert after['tables']['mp_job'] == dict(
        rows_observed=100001, count_is_lower_bound=True, rows_until_limit=0, status='over_limit',
    )
    raw = site.sql(state, 'history-rows-after', "SELECT count(*) FROM mp_job WHERE state='completed';")
    assert raw.decode().strip() == '100002'
    record = dict(image=state['image_id'], empty=before, populated=after, completed_rows_after=100002)
    write(site.local / 'history-cli-result.json', record)
    print(json.dumps(record))


if __name__ == '__main__':
    run()
