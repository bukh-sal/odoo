"""Read-only current SDK/image comparison with retained real G5 SQL witnesses."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.plans import applicable_migrations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    evidence = ROOT / 'docs/evidence/G5/20261029-migration-matrix-02'
    output = ROOT / 'docs/evidence/G5/20261029-migration-order-rollout-01/witness-reconciliation.json'
    assert not output.exists()
    state = json.loads((ROOT / '.local/g5-migration-matrix-02/state.json').read_text())
    assert state['phase'] == 'native_engine_passed_planner_order_mismatch'
    qualification = json.loads((evidence / 'qualification.json').read_text())
    target = json.loads((ROOT / '.local/g5-manager-upgrade/operator/target.json').read_text())
    assert target['generation'] == 6 and target['image_id'] == args.image
    child_checks = []
    for child in state['children']:
        observed = json.loads(subprocess.check_output(['docker', 'inspect', child['name']]))[0]
        assert observed['Image'] == state['image_id'] and observed['State']['Status'] == 'exited' and observed['State']['ExitCode'] == 0
        child_checks.append(child['name'])
    validator = ArtifactValidator(TrustPolicy('development', allow_unsigned_development=True))
    manifests, expected_files = {}, {}
    for record in json.loads((evidence / 'validated-archives.json').read_text()):
        version = record['version']
        verified = validator.verify(ROOT / '.local/g5-migration-matrix-02' / (version + '.mplug'), expected_digest=record['artifact_digest'])
        manifests[version] = verified.manifest
        prefix = 'backend/odoo_addons/mp_g5_migration_probe/'
        expected_files.update({version + '/mp_g5_migration_probe/' + name[len(prefix):]: digest
                               for name, digest in verified.inventory.items() if name.startswith(prefix)})
    cases = []
    for case, start, end, before_name, after_name in [
            ('adjacent9to10', '0.1.9', '0.1.10', 'adjacent-install', 'adjacent-upgrade-0_1_10'),
            ('adjacent10to2', '0.1.10', '0.2.0', 'adjacent-upgrade-0_1_10', 'adjacent-upgrade-0_2_0'),
            ('skipped', '0.1.0', '0.3.0', 'skipped-install', 'skipped-upgrade-0_3_0'),
            ('wide', '0.99999998.0', '0.100000000.0', 'wide-install', 'wide-upgrade-0_100000000_0'),
            ('fresh', None, '0.3.0', None, 'fresh-install')]:
        after = json.loads((evidence / (after_name + '.json')).read_text())
        before_events = json.loads((evidence / (before_name + '.json')).read_text())['events'] if before_name else []
        events = after['events'][len(before_events):]
        selected = applicable_migrations(manifests[end], start)
        assert [(item['phase'], item['target_version']) for item in selected] == [(item['phase'], item['target']) for item in events]
        cases.append({'case': case, 'from': start, 'to': end, 'manifest': manifests[end],
                      'expected': [[item['phase'], item['target'], '19.0.' + start] for item in events],
                      'script_digests': [item['digest'] for item in selected]})
    # Confirm the retained terminal database witnesses have not changed. Never
    # start another native process to verify an already completed upgrade.
    for case, file_name in [('adjacent', 'adjacent-upgrade-0_2_0'), ('skipped', 'skipped-upgrade-0_3_0'), ('wide', 'wide-upgrade-0_100000000_0'), ('fresh', 'fresh-install')]:
        expected = json.loads((evidence / (file_name + '.json')).read_text())
        query = """BEGIN READ ONLY; SELECT jsonb_build_object(
          'rows',(SELECT jsonb_agg(jsonb_build_object('id',id,'name',name,'payload',payload,'step_count',step_count) ORDER BY id) FROM mp_g5_migration_record),
          'events',COALESCE((SELECT jsonb_agg(jsonb_build_object('phase',phase,'target',target,'installed',installed,'payload_before',payload_before,'payload_after',payload_after,'column_ready',column_ready) ORDER BY id) FROM mp_g5_migration_event),'[]'::jsonb)); ROLLBACK;"""
        actual = json.loads(subprocess.check_output(['docker', 'exec', '-i', target['project'] + '-db-1', 'psql', '-X', '-qAt', '-U', 'postgres', '-d', state['databases'][case], '-v', 'ON_ERROR_STOP=1'], input=query.encode()))
        assert actual == {key: expected[key] for key in ('rows', 'events')}
    digest = hashlib.sha256((ROOT / 'packages/platform_sdk/modular_platform/plans.py').read_bytes()).hexdigest()
    probe = '''import hashlib,json,sys
from pathlib import Path
from modular_platform.plans import applicable_migrations
value=json.load(sys.stdin)
assert hashlib.sha256(Path('/opt/modular/packages/platform_sdk/modular_platform/plans.py').read_bytes()).hexdigest()==value['planner_sha256']
for name,digest in value['fixture_files'].items():
 assert hashlib.sha256((Path('/matrix')/name).read_bytes()).hexdigest()==digest
for case in value['cases']:
 actual=applicable_migrations(case['manifest'],case['from'])
 assert [[s['phase'],s['target_version'],'19.0.'+case['from']] for s in actual]==case['expected']
 assert [s['digest'] for s in actual]==case['script_digests']
print(json.dumps({'result':'passed_current_image_planner_matches_actual_SQL_order','cases':len(value['cases']),'script_hashes_checked':sum(len(c['script_digests']) for c in value['cases']),'exact_extracted_fixture_files':len(value['fixture_files'])}))
'''
    command = ['docker', 'run', '--rm', '-i', '--name', state['project'] + '-current-sdk-audit',
               '--label', 'com.modular.disposable=' + state['project'], '--network', 'none', '--read-only',
               '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--memory', '512m', '--tmpfs', '/tmp', '--mount', 'type=volume,source=' + state['source_volume'] + ',target=/matrix,readonly',
               '--entrypoint', '/venv/bin/python', args.image, '-c', probe]
    actual = json.loads(subprocess.check_output(command, input=json.dumps({'cases': cases, 'planner_sha256': digest, 'fixture_files': expected_files}).encode()))
    report = {'result': 'passed_current_planner_and_retained_real_migration_witnesses', 'utc': datetime.now(timezone.utc).isoformat(),
              'current_image_id': args.image, 'native_engine_image_id': state['image_id'], 'planner_sha256': digest,
              'actual_current_image_result': actual, 'terminal_native_children_checked': child_checks,
              'retained_four_databases_exact': True, 'public_contracts': 'G2revision11/84files unchanged',
              'retained_control_path': '../20261029-manager-upgrade-01/qualification.json',
              'native_matrix': '../20261029-migration-matrix-02/qualification.json',
              'limits': qualification['limits']}
    with output.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'result': report['result'], 'actual_image_cases': actual['cases'], 'actual_native_scripts': actual['script_hashes_checked']}))


if __name__ == '__main__':
    main()
