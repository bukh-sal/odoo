"""Measure the selected stock kit with a disposable 10,000-note workspace."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
from statistics import median
import subprocess
import sys
from threading import Barrier
from time import perf_counter, sleep


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'release'))
from check_reference import Client
from initialize_reference import Reference, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18107)
    parser.add_argument('--reuse-seeded', action='store_true')
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Fresh benchmark evidence path required')
    reference = Reference(args)
    state = reference.state()
    target = load(reference.local / 'operator/target.json')
    assert state['phase'] == 'kit_backend_worker_reference_qualified' and state['port'] == args.port
    assert target['image_id'] == reference.manifest['images']['application']['image_id']
    assert target['sites'][0]['database'] == state['database'] and state['database'].startswith('mp_disposable_r0_r1_release_')
    resources = {}
    for role, container in [('application', target['worker_id']), ('database', state['project'] + '-db-1')]:
        settings = subprocess.check_output(['docker', 'inspect', '--format',
            '{{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}', container], timeout=30).decode().split()
        resources[role] = {'nano_cpus': int(settings[0]), 'memory_bytes': int(settings[1])}
    cpu, memory, driver = subprocess.check_output(['docker', 'info', '--format',
        '{{.NCPU}} {{.MemTotal}} {{.Driver}}'], timeout=30).decode().split()
    resources['docker'] = {'logical_cpus': int(cpu), 'memory_bytes': int(memory), 'storage_driver': driver}

    def sql(query):
        return subprocess.check_output(['docker', 'exec', '-i', state['project'] + '-db-1', 'psql',
            '-XqAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', state['database']],
            input=query.encode(), timeout=60).decode().strip()

    fixture = load(reference.local / 'fixtures.json')
    workspace_id = int(fixture['workspaces']['A']['id'])
    count = sql(f'SELECT count(*) FROM mp_example_note WHERE workspace_id={workspace_id};')
    # SQL only creates synthetic benchmark data in this disposable database.
    # All timed reads go through ordinary scoped HTTP and native ORM paths.
    if args.reuse_seeded:
        assert count == '10000'
        assert sql(f"SELECT count(*) FROM mp_example_note WHERE workspace_id={workspace_id} AND title LIKE 'Stock benchmark %';") == '9999'
    else:
        assert count == '1'
        sql(f'''INSERT INTO mp_example_note
        (workspace_id, public_id, title, body, author_id, revision, create_uid, write_uid, create_date, write_date)
        SELECT n.workspace_id, gen_random_uuid()::text, 'Stock benchmark ' || lpad(i::text,5,'0'),
               repeat(md5(i::text),300), n.author_id, 1, n.create_uid, n.write_uid,
               timezone('UTC',now()), timezone('UTC',now())
        FROM mp_example_note n CROSS JOIN generate_series(1,9999) i WHERE n.workspace_id={workspace_id};''')
    sql('ANALYZE mp_example_note;')
    def snapshot():
        return sql(f"SELECT count(*) || ':' || md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) "
                   f"FROM mp_example_note n WHERE workspace_id={workspace_id};")
    before = snapshot()
    assert before.startswith('10000:')
    ident = int(sql(f"SELECT id FROM mp_example_note WHERE workspace_id={workspace_id} AND title='Stock benchmark 00100';"))
    clients = [Client(reference, 'alice') for _ in range(20)]
    assert clients[0].native('mp.example.note', 'search_count', [[]], workspace='B') == 1
    assert clients[0].native('mp.example.note', 'search_count', [[]]) == 10000
    prefix = 'Stock benchmark 00'
    pages = [clients[0].native('mp.example.note', 'web_search_read', kwargs={
        'domain': [['title', 'ilike', prefix]], 'limit': 80, 'offset': offset,
        'order': 'title,id', 'specification': {'title': {}},
    })['records'] for offset in (0, 80)]
    assert all(len(page) == 80 and all(row['title'].startswith(prefix) for row in page) for page in pages)
    assert not {row['id'] for row in pages[0]} & {row['id'] for row in pages[1]}

    def request(client, case):
        if case == 'native_list80':
            rows = client.native('mp.example.note', 'web_search_read', kwargs={
                'domain': [], 'offset': 0, 'limit': 80,
                'specification': {key: {} for key in ('title', 'revision', 'write_date', 'x_notes_labels')}})
            assert len(rows['records']) == 80 and all(row['title'].startswith('Stock benchmark ') for row in rows['records'])
        else:
            row, = client.native('mp.example.note', 'web_read', [[ident]], {
                'specification': {key: {} for key in ('title', 'body', 'revision', 'x_notes_labels')}})
            assert row['id'] == ident and len(row['body']) == 9600

    cases = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        for case in ('native_list80', 'native_detail'):
            for _ in range(3):
                request(clients[0], case)
            samples = []
            for _ in range(10):
                barrier = Barrier(20)

                def timed(client):
                    barrier.wait(timeout=10)
                    start = perf_counter()
                    request(client, case)
                    return round((perf_counter() - start) * 1000, 3)

                samples.extend(pool.map(timed, clients))
                sleep(1.15)
            p95 = sorted(samples)[math.ceil(.95 * len(samples)) - 1]
            cases[case] = {'count': len(samples), 'median_ms': median(samples), 'p95_ms': p95,
                           'max_ms': max(samples), 'samples_ms': samples}
    assert snapshot() == before
    result = {'result': 'passed' if all(row['p95_ms'] < 500 for row in cases.values()) else 'target_missed',
              'image': target['image_id'], 'generation': target['generation'], 'note_count': 10000,
              'workspace_digest_unchanged': True, 'concurrent_sessions': 20, 'resources': resources, 'cases': cases,
              'scoped_server_filter_and_disjoint_pagination': True,
              'comparison_limit': 'Same documented p95 target and burst pattern as the historical R1 read check. A separate fixture and shared host preclude a causal speed comparison.'}
    with args.receipt.open('x', encoding='utf8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'result': result['result'], 'p95_ms': {key: row['p95_ms'] for key, row in cases.items()}}))
    return int(result['result'] != 'passed')


if __name__ == '__main__':
    sys.exit(main())
