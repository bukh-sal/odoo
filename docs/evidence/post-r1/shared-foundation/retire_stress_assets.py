"""Retire exact Docker assets after both disposable stress sites are verified."""

import argparse
import json
from pathlib import Path
import re
import subprocess

from stress_sites import ADDONS, StressSite, load, write


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, encoding='utf8', timeout=90).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('build_receipts', nargs='+', type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Use a fresh retirement receipt')
    owned = []
    operations = set()
    for key in ADDONS:
        local = StressSite(argparse.Namespace(site=key)).local
        for phase in (('install', 'upgrade', 'fault-recover') if key == 'aurora' else ('install', 'upgrade')):
            row = load(local / (phase + '.json'))
            assert row['phase'] == 'verified' or phase == 'install' and load(local / 'verify-install.json')['business_preserved']
            operations.add(row['operation_id'])
        assert load(local / 'http-successor.json')['native_workflow_record_preserved']
        owned.append(load(local / 'state.json'))

    images = {row['image_id']: row['tag'] for row in (load(path) for path in args.build_receipts)}
    tag_names = set(images.values()) | {'modular-platform:retained-' + operation for operation in operations}
    listed = docker('ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.Names}}').splitlines()
    removable = []
    for site in owned:
        project = site['project']
        assert re.fullmatch(r'mp-r0-r1release[0-9a-f]{12}', project)
        ids = [ident for ident, name in (row.split(' ', 1) for row in listed) if name.startswith(project + '-')]
        containers = json.loads(docker('inspect', *ids))
        assert len(containers) == len(ids)
        for container in containers:
            labels = container['Config']['Labels']
            assert (labels.get('com.docker.compose.project') == project or labels.get('com.modular.disposable') == project
                    or labels.get('com.modular.deployment') == site['deployment_id'])
        resources = site['owned_resources']
        volumes = [row['Name'] for row in json.loads(docker('volume', 'inspect', *resources['volumes']))
                   if row['Labels'].get('com.modular.disposable') == project]
        networks = [row['Name'] for row in json.loads(docker('network', 'inspect', *resources['networks']))
                    if row['Labels'].get('com.modular.disposable') == project]
        assert set(volumes) == set(resources['volumes']) and set(networks) == set(resources['networks'])
        removable.append((project, ids, volumes, networks))

    retired = {'projects': {}, 'image_tags': []}
    for project, ids, volumes, networks in removable:
        docker('rm', '-f', '-v', *ids)
        docker('volume', 'rm', *volumes)
        docker('network', 'rm', *networks)
        retired['projects'][project] = {'containers_removed': len(ids), 'volumes_removed': volumes, 'networks_removed': networks}
        write(args.receipt, retired)

    for image in images:
        if docker('ps', '-aq', '--filter', 'ancestor=' + image):
            raise ValueError('Image remains in use by a container')
        descriptor, = json.loads(docker('image', 'inspect', image))
        tags = set(descriptor['RepoTags'])
        assert tags and tags <= tag_names
        docker('image', 'rm', *sorted(tags))
        retired['image_tags'].extend(sorted(tags))
        write(args.receipt, retired)
    retired['result'] = 'retired_owned_docker_assets'
    write(args.receipt, retired)
    print(json.dumps(retired))


if __name__ == '__main__':
    main()
