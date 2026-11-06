"""Retire only the recorded stock kit rehearsal containers and storage."""

import argparse
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[4]
OWNED = ROOT / '.local/stock-webclient-release'


def docker(*args):
    return subprocess.check_output(['docker', *args], timeout=90)


def load(path):
    return json.loads(path.read_bytes())


def matching_containers(nonce):
    return docker('ps', '-aq', '--no-trunc', '--filter', 'name=' + nonce).decode().split()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', choices=('clean', 'clean-02', 'clean-rtl', 'clean-final', 'clean-stock'))
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    assert not args.receipt.exists()
    local = OWNED / args.work / 'private/reference'
    state = load(local / 'state.json')
    worker = load(local / 'worker/state.json')
    target = load(local / 'operator/target.json')
    assert state['phase'] == 'kit_backend_worker_reference_qualified'
    if args.work == 'clean':
        assert load(local / 'stock-rtl-transition.json')['phase'] == 'passed'
    if args.work == 'clean-rtl':
        assert load(local / 'stock-final-transition.json')['phase'] == 'passed'
    if args.work == 'clean-final':
        assert load(local / 'stock-qualified-transition.json')['phase'] == 'passed'
    project = state['project']
    nonce = re.fullmatch(r'mp-r0-r1release([0-9a-f]{12})', project).group(1)
    assert state['port'] == {'clean': 18106, 'clean-02': 18107, 'clean-rtl': 18108,
                             'clean-final': 18109, 'clean-stock': 18110}[args.work]
    worker_project = worker['project']
    assert worker_project == 'mp-disposable-document-stats-release-' + nonce
    assert target['project'] == project and target['deployment_id'] == state['deployment_id']
    ids = matching_containers(nonce)
    assert ids
    containers = json.loads(docker('inspect', *ids))
    volumes = sorted(set(state['owned_resources']['volumes'] + worker['volumes']))
    networks = sorted(state['owned_resources']['networks'])
    assert len(volumes) == 8 and len(networks) == 2
    for container in containers:
        name = container['Name'].lstrip('/')
        labels = container['Config']['Labels']
        assert name.startswith((project + '-', worker_project + '-'))
        assert (labels.get('com.docker.compose.project') in {project, worker_project}
                or labels.get('com.modular.disposable') == project
                or labels.get('com.modular.deployment') == state['deployment_id']), name
        assert not container['State']['Restarting']
    for volume in json.loads(docker('volume', 'inspect', *volumes)):
        assert volume['Labels']['com.modular.disposable'] == project
    for network in json.loads(docker('network', 'inspect', *networks)):
        assert network['Labels']['com.modular.disposable'] == project
        assert set(network['Containers']) <= set(ids)
    retained = {
        'project': project, 'port': state['port'],
        'containers': {item['Name'].lstrip('/'): item['Id'] for item in containers},
        'volumes': volumes, 'networks': networks, 'retired': False,
    }
    with args.receipt.open('x', encoding='utf-8') as file:
        json.dump(retained, file, indent=2)
    running = [item['Id'] for item in containers if item['State']['Running']]
    if running:
        docker('stop', *running)
    docker('rm', '-v', *ids)
    docker('volume', 'rm', *volumes)
    docker('network', 'rm', *networks)
    assert not matching_containers(nonce)
    retained['retired'] = True
    args.receipt.write_text(json.dumps(retained, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(project=project, containers=len(ids), volumes=len(volumes), networks=len(networks))))


if __name__ == '__main__':
    main()
