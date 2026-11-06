"""Record the exact clean and recovered stock qualification without credentials."""

import argparse
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'release'))
from check_reference import Client
from initialize_reference import load


def write(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)
        output.write('\n')


def preflight(local, operation):
    report = load(local / 'operator/control/stages' / operation / 'assets.json')
    assert report['result'] == 'prepared'
    rtl = [row for row in report['assets'] if row['url'].endswith('.rtl.min.css')]
    assert {row['url'].rsplit('/', 1)[-1] for row in rtl} == {
        'web.assets_web.rtl.min.css', 'web.assets_web_print.rtl.min.css'}
    assert all(re.fullmatch(r'/web/assets/[0-9a-f]{64}/[^/]+', row['url']) for row in rtl)
    return rtl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('fresh', 'transition'))
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--kit', type=Path, default=ROOT / '.local/releases/stock-0.1.28-rtl')
    parser.add_argument('--work', choices=('clean', 'clean-rtl', 'clean-final', 'clean-stock'))
    args = parser.parse_args()
    folder = args.work or ('clean-rtl' if args.mode == 'fresh' else 'clean')
    local = ROOT / '.local/stock-webclient-release' / folder / 'private/reference'
    state = load(local / 'state.json')
    target = load(local / 'operator/target.json')
    expected = load(args.kit / 'images.json')['images']['application']['image_id']
    assert target['image_id'] == expected and target['project'] == state['project']
    assert state['phase'] == 'kit_backend_worker_reference_qualified'
    worker = load(local / 'worker/job-qualified.json')
    if args.mode == 'fresh':
        record = load(local / 'reference-checks.json')
        assert record['phase'] == 'passed' and len(record['checks']) == 5
        assert worker['job']['state'] == 'completed' and worker['job']['attempts'] == 1
        result = dict(result='passed', image=expected, generation=target['generation'],
            backend_checks=record['checks'], notes=2, canvas_boards=1, worker_one_attempt=True,
            worker_publication_generation=worker['publication_generation'], result_statistics=worker['job']['result']['statistics'])
        if folder == 'clean-stock':
            result['preflight_rtl_assets'] = preflight(local, load(local / 'worker/integration.json')['connector']['operation_id'])
        write(args.receipt, result)
        return
    transition_file = {'clean': 'stock-rtl-transition.json', 'clean-rtl': 'stock-final-transition.json',
                       'clean-final': 'stock-qualified-transition.json'}[folder]
    record = load(local / transition_file)
    assert record['phase'] == 'passed' and record['successor_image'] == expected
    assert record['restored_native_scope'] and record['successor_native_scope']
    assert record['failure']['state'] == 'recovery_required' and not record['failure']['traffic_resumed']
    updated = state | {'database': target['sites'][0]['database']}
    client = Client(SimpleNamespace(local=local, state=lambda: updated), 'alice')
    note = load(local / 'reference-checks.json')['notes']['A']['id']
    preserved = client.service('org.example.notes_stats', 'jobs', 'status', dict(note_id=note))['job']
    assert preserved == worker['job']
    result = dict(result='passed', image=expected, previous_image=record['base_image'],
        initial_generation=record['initial_generation'], selected_generation=record['generation'],
        fault_operation=record['fault_operation'], fault_traffic_open=False, failure_checkpoint=record['failure']['backup_id'],
        fault_review=record['fault_plan'], normal_review=record['normal_plan'], normal_operation=record['normal_operation'],
        restore_decision_hash=record['restore_decision_hash'], resume_decision_hash=record['resume_decision_hash'],
        fresh_restore=True, restored_and_successor_scope=True, business_rows_and_memberships_preserved=True,
        checkpoint_files=record['checkpoint_files'], original_filestore_preserved=True,
        original_worker_and_completed_job_preserved=True)
    if folder == 'clean-final':
        result['preflight_rtl_assets'] = preflight(local, record['normal_operation'])
    write(args.receipt, result)


if __name__ == '__main__':
    main()
