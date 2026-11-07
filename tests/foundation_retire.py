"""Retire only the explicitly recorded CF targets, never global Docker assets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from foundation_release import ROOT, load, write
from modular_platform.operator_store import OperatorStore


def docker(*args):
    return subprocess.check_output(['docker', *args], timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    assert not args.receipt.exists()
    selected = []
    for key in ('aurora', 'maintenance'):
        local = ROOT / '.local/foundation-release/cf-01' / key
        state, target = load(local / 'state.json'), load(local / 'operator/target.json')
        assert state['project'] == target['project']
        store = OperatorStore(local / 'operator/control')
        for path in [local / 'notes-install.json', local / 'background-install.json',
                     *local.glob('upgrade*.json'), *local.glob('fault*.json')]:
            record = load(path)
            assert record['phase'] == 'verified', path.name
            operation = record.get('operation_id') or record['operation']
            assert store.status(operation)['state'] in ('completed', 'revoked')
        ids = docker('ps', '-aq', '--filter', 'name=' + target['project']).decode().split()
        rows = json.loads(docker('inspect', *ids)) if ids else []
        keep = {target['worker_id'], target['project'] + '-db-1', target['project'] + '-edge-1'}
        for row in rows:
            name = row['Name'].lstrip('/')
            assert name.startswith(target['project'] + '-')
            labels = row['Config']['Labels'] or {}
            assert (labels.get('com.modular.disposable') == target['project']
                    or labels.get('com.modular.deployment') == target['deployment_id']
                    or labels.get('com.docker.compose.project') == target['project'])
            if row['Id'] in keep or name in keep or row['State']['Running'] or '-job-' in name:
                continue
            assert row['State']['Status'] == 'exited'
            assert row['State']['ExitCode'] == 0 or name == target['project'] + '-cf-background-seed'
            selected.append(dict(id=row['Id'], name=name, image=row['Image'], exit_code=row['State']['ExitCode']))
    # No active journal/helper is removed; private diagnostics/checkpoints and
    # every volume/image/live worker remain. Recheck exact immutable IDs first.
    for row in selected:
        current, = json.loads(docker('inspect', row['id']))
        assert not current['State']['Running'] and current['Image'] == row['image']
    if selected:
        docker('rm', *(row['id'] for row in selected))
    report = dict(result='retired_owned_terminal_helpers', utc=datetime.now(timezone.utc).isoformat(),
                  containers=selected, removed=len(selected), images_removed=0, volumes_removed=0,
                  live_roles_and_private_diagnostics_preserved=True)
    write(args.receipt, report)
    print(json.dumps(dict(result=report['result'], removed=len(selected))))


if __name__ == '__main__':
    main()
