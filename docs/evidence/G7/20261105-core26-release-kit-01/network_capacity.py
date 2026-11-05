"""Release two unused archived fixture subnets after a pre-data refusal."""
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess

ROOT = Path.cwd().resolve()
OUT = Path(__file__).parent
WORK = ROOT / '.local/release-kit-core26-rehearsal/private'
failed = WORK / 'reference'
retained = WORK / 'reference-before-network-capacity'
targets = {
    '9652329b374d9cdc8a4abfa27e2d5b0539379e8a318c87dfa62cc66631694de4': 'mp-r0-20261027234238n_edge',
    'e8b487dac8c3ab45634913f56553860498fed2c0250de329b90bddcea1e3bcb1': 'mp-r0-20261027234238n_runtime',
}
project = 'mp-r0-20261027234238n'


def docker(*args):
    return subprocess.check_output(['docker', *args], timeout=30, text=True)


state = json.loads((failed / 'state.json').read_bytes())
assert state['phase'] == 'creating_owned_networks'
assert state['project'] == 'mp-r0-r1release41549b7c538c'
error = (failed / 'logs/network-runtime.stderr').read_text().strip()
assert 'all predefined address pools have been fully subnetted' in error
assert not any(path.exists() for path in (failed / 'compose.json', failed / 'account-passwords.json'))
assert state['project'] not in docker('network', 'ls', '--format', '{{.Name}}')
assert state['project'] not in docker('volume', 'ls', '--format', '{{.Name}}')
assert not docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + state['project']).strip()
assert failed.resolve() == ROOT / '.local/release-kit-core26-rehearsal/private/reference'
assert retained.resolve().parent == failed.resolve().parent and not retained.exists()

archived = json.loads((ROOT / 'docs/evidence/G7/20261102-docker-retention-01/container-retirement.json').read_bytes())
assert archived['by_project'][project] == 3
assert project in json.loads((ROOT / '.local/g7-docker-retention/project-inventory.json').read_bytes())
before = set(docker('network', 'ls', '--no-trunc', '--format', '{{.ID}}').splitlines())
for network_id, name in targets.items():
    row = json.loads(docker('network', 'inspect', network_id))[0]
    assert row['Name'] == name and row['Id'] == network_id and not row['Containers']
    assert row['Labels']['com.docker.compose.project'] == project
    assert not docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project).strip()
    containers = docker('ps', '-aq').splitlines()
    for container in json.loads(docker('inspect', *containers)):
        assert name not in (container['NetworkSettings'].get('Networks') or {})
    assert docker('network', 'rm', network_id).strip() == network_id
assert set(docker('network', 'ls', '--no-trunc', '--format', '{{.ID}}').splitlines()) == before - set(targets)
failed.rename(retained)

with (OUT / 'network-capacity.json').open('x', encoding='utf8') as handle:
    json.dump({
        'result': 'pre_data_refusal_retained_and_two_archived_subnets_released',
        'utc': datetime.now(timezone.utc).isoformat(), 'failed_phase': state['phase'],
        'failed_project': state['project'], 'daemon_error': error,
        'failed_project_created_networks_volumes_containers': 0,
        'retained_diagnostics': retained.relative_to(ROOT).as_posix(),
        'retired_archived_networks': targets, 'other_networks_preserved': True,
        'containers_volumes_images_removed': 0,
    }, handle, indent=2)
    handle.write('\n')
print('Retained the pre-data refusal and released two archived fixture subnets')
