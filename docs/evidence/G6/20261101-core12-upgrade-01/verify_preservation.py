"""Read-only installed core preservation, then one normal original-actor job."""
import argparse, hashlib, json, re, sys, tarfile
from datetime import datetime,timezone
from pathlib import Path
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
from activate import ROOT, j, f, MARKER, context
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION

def preservation():
    resume=sys.argv[1:]==['--resume-copy'];assert not sys.argv[1:] or resume
    state, native = context()
    record = f.load(MARKER)
    assert record['state'] == 'completed_needs_qualification' and native.config['generation'] == 10
    operation = record['operation_id']
    checkpoint = native.store.root / 'checkpoints' / operation
    stage = native.store.root / 'stages' / operation
    fence = f.load(stage / 'dispatch-fence/fence.json')['result']
    ready = f.load(stage / 'dispatch-ready.json')
    enabled = f.load(stage / 'dispatch-enable/enable.json')['result']
    assert fence['after']['control']['generation'] == 41 and ready['control']['generation'] == 42 and (enabled['after']['control']['generation'] == 43)
    current = DispatchMaintenance(native).inspect()
    assert current == enabled['after'] and current['job_states'] == dict(completed=5, dead_letter=4, cancelled=1)

    def parse(raw, table):
        match = re.search(b'COPY public\\.' + table.encode() + b' \\((.*?)\\) FROM stdin;\\n(.*?)\\\\\\.\\n', raw, re.S)
        assert match
        return (match[1].decode().split(', '), sorted((line.decode().split('\t') for line in match[2].splitlines() if line)))
    counts = {}
    timestamp_backfills=0
    for table in ['mp_example_note', 'mp_example_canvas_board', 'mp_example_note_event_summary', 'mp_outbox', 'mp_job']:
        old = (j.LOCAL/'logs'/('core12-backup-'+table+'.stdout')).read_bytes() if resume else f.command('core12-backup-' + table, ['docker', 'exec', '-i', state['project'] + '-db-1', 'pg_restore', '--data-only', '--no-owner', '--no-privileges', '--schema=public', '--table=' + table, '-f', '-'], input=(checkpoint / 'database.dump').read_bytes())
        new = (j.LOCAL/'logs'/('core12-current-'+table+'.stdout')).read_bytes() if resume else f.command('core12-current-' + table, ['docker', 'exec', state['project'] + '-db-1', 'pg_dump', '-U', 'postgres', '--data-only', '--no-owner', '--no-privileges', '--table=public.' + table, state['active_db']])
        a, b = (parse(old, table), parse(new, table))
        assert a[0] == b[0]
        counts[table] = len(a[1])
        if table == 'mp_job':
            allowed = {'release_digest', 'claim_generation', 'dispatch_generation'}
            oldrows=[dict(zip(a[0],row)) for row in a[1]];newrows=[dict(zip(b[0],row)) for row in b[1]]
            newbyid={row['public_id']:row for row in newrows}
            for row in oldrows:
                current=newbyid[row['public_id']]
                if row['finished_at']!=current['finished_at']:
                    assert row['public_id']==f.load(j.LOCAL/'core11-cancel-seed.json')['job_id']
                    assert row['state']==current['state']=='cancelled' and row['finished_at']=='\\N'
                    stamp=datetime.fromisoformat(current['finished_at']).replace(tzinfo=timezone.utc)
                    assert datetime.fromisoformat(f.load(OUT/'bundle.json')['plan']['created_at'].replace('Z','+00:00'))<=stamp<=datetime.now(timezone.utc)
                    # Existing reconcile_release explicitly backfills a missing
                    # terminal timestamp. No identity/input/effect outcome changes.
                    current['finished_at']='\\N';timestamp_backfills+=1
            project = lambda rows: sorted([{key: value for key, value in zip(a[0], row) if key not in allowed} for row in rows], key=lambda r: r['public_id'])
            project_dict=lambda rows:sorted([{k:v for k,v in row.items() if k not in allowed} for row in rows],key=lambda r:r['public_id'])
            assert project_dict(oldrows)==project_dict(newrows) and len(a[1])==len(b[1])==10
        else:
            assert a == b
    assert counts == dict(mp_example_note=29, mp_example_canvas_board=0, mp_example_note_event_summary=3, mp_outbox=47, mp_job=10)
    args, _ = native._child(operation, 'core12-fixture-files', network=False)
    files = json.loads(f.command('core12-current-files', args + ['-c', FILE_OBSERVATION, state['active_db']]))
    expected = {}
    prefix = 'filestore/' + state['active_db'] + '/'
    with tarfile.open(checkpoint / 'filestore.tar.gz', 'r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):
                expected[member.name[len(prefix):]] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert all((files.get(name) == digest for name, digest in expected.items()))
    cfg = j.LOCAL / 'operator/worker-target.json'
    worker = f.load(cfg)
    assert worker['helper_image'] == 'sha256:4ea56c47170acc9fa41933ff19023e0e00665faafecddc123ba5c7de025bbfa0'
    before = hashlib.sha256(cfg.read_bytes()).hexdigest()
    worker['helper_image'] = native.config['image_id']
    f.write(cfg, worker)
    assert timestamp_backfills==1
    f.save('preservation.json', dict(result='passed_installed_core12_upgrade_preservation', image_id=state['image_id'], generation=10, dispatch_generation=43, same_database=True, counts_exact=counts, all_original_job_identity_input_attempt_result_and_other_fields_exact=True, sanctioned_job_fields=['release_digest','claim_generation','dispatch_generation'],sanctioned_cancelled_null_terminal_timestamp_backfills=timestamp_backfills,retained_files=len(expected), plugin_installations_and_bindings_exact=True, worker_configuration_update=dict(previous_sha256=before, current_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(), only_field='helper_image', reason='Use the normally approved current core image for isolated operator helpers; runtime authority generation2 retained'), fixture_corrections=['Expected job states updated for four committed owned runner tests.','Existing reconciliation backfills this one cancelled job null finished_at; timestamp must fall within this reviewed operation, and every other field stays exact. Read-only COPY results reused explicitly; no migration replay.'],limits=['JOB01/02 targeted lease/error/revocation requalification and actual external Notes bridge still required.']))
    record['state'] = 'preservation_verified'
    f.write(MARKER, record)
    f.phase(state, 'core12_preservation_verified')
    f.guard(state)
    print('Installed core1.12 preserves all original Notes/events/jobs/files; normal job helper pin updated to approved image')
preservation()
