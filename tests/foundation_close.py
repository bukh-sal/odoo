"""Final exact-owned Docker retirement after the consolidated qualification."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import subprocess

from foundation_release import ROOT, load, write
from foundation_lifecycle import sql
from modular_platform.operator_store import OperatorStore


def docker(*args):
    return subprocess.check_output(['docker', *args], timeout=120)


def main():
    local = ROOT / '.local/foundation-release'
    output = ROOT / 'docs/evidence/post-r1/foundation-release/final-docker-retirement.json'
    intent = local / 'retirement-intent.json'
    assert not intent.exists() and not output.exists(), 'Reconcile existing retirement before continuing'
    evidence = output.parent
    assert load(evidence / 'cf-04-decision.json')['result'] == 'passed'
    assert load(evidence / 'cf-05-runtime.json')['result'] == 'passed_CF_K'
    assert load(evidence / 'cf-05-privacy.json')['result'] == 'passed_finite_known_values'
    assert load(local / 'clean-provision.json')['phase'] == 'verified'
    paths = [local / 'cf-01' / key for key in ('aurora', 'maintenance')]
    paths += [local / 'clean-core46/private/reference']
    containers, networks, volumes, operations = [], [], [], set()
    for path in paths:
        state, target = load(path / 'state.json'), load(path / 'operator/target.json')
        project = target['project']
        assert re.fullmatch(r'mp-r0-r1release[0-9a-f]{12}', project) and state['project'] == project
        store = OperatorStore(path / 'operator/control')
        with sqlite3.connect(store.database.as_uri() + '?mode=ro', uri=True) as db:
            ids = [row[0] for row in db.execute('SELECT operation_id FROM operations')]
        for operation in ids:
            assert store.status(operation)['state'] in ('completed', 'revoked'), operation
        operations.update(ids)
        assert sql(target, "SELECT count(*) FROM mp_job WHERE state IN ('running','outcome_unknown');") == '0'
        if sql(target, "SELECT to_regclass('mp_background_report') IS NOT NULL;") == 't':
            assert sql(target, "SELECT count(*) FROM mp_background_report WHERE state='running' OR snapshot IS NOT NULL;") == '0'
        ids = docker('ps', '-aq', '--no-trunc', '--filter', 'name=' + project).decode().split()
        rows = json.loads(docker('inspect', *ids)) if ids else []
        owned = {row['Id'] for row in rows}
        for row in rows:
            name = row['Name'].lstrip('/')
            labels = row['Config']['Labels'] or {}
            assert name.startswith(project + '-')
            assert (labels.get('com.modular.disposable') == project
                    or labels.get('com.modular.deployment') == target['deployment_id']
                    or labels.get('com.docker.compose.project') == project)
            assert not row['State']['Paused']
            assert not row['State']['Running'] or '-op-' not in name
            assert not row['State']['Running'] or '-job-' not in name, 'Drain reviewed lanes first'
            containers.append(dict(id=row['Id'], name=name, image=row['Image'], running=row['State']['Running']))
        expected_volumes = {project + '_' + role for role in ('appconfig', 'dbconfig', 'bootstrap', 'proxyconfig', 'filestore', 'pgdata')}
        assert set(state['owned_resources']['volumes']) == expected_volumes
        for name in sorted(expected_volumes):
            row, = json.loads(docker('volume', 'inspect', name))
            assert row['Labels']['com.modular.disposable'] == project
            attached = set(docker('ps', '-aq', '--no-trunc', '--filter', 'volume=' + name).decode().split())
            assert attached <= owned
            volumes.append(name)
        expected_networks = {project + '_runtime', project + '_edge'}
        assert set(state['owned_resources']['networks']) == expected_networks
        for name in sorted(expected_networks):
            row, = json.loads(docker('network', 'inspect', name))
            assert row['Labels']['com.modular.disposable'] == project
            assert set((row.get('Containers') or {}).keys()) <= owned
            networks.append(name)
    build_names = ['cf01-baseline-02', 'cf02-foundation-current-01', 'cf02-foundation-repro-01',
                   'cf02-foundation46-current-01', 'cf02-foundation46-repro-01']
    builds = [load(ROOT / 'docs/evidence/G7' / name / 'candidate-build.json') for name in build_names]
    final = builds[3]['image_id']
    allowed_tags = {row['tag'] for row in builds} | {'modular-platform:retained-' + operation for operation in operations}
    images = []
    for record in builds:
        row, = json.loads(docker('image', 'inspect', record['image_id']))
        tags = set(row.get('RepoTags') or [])
        assert tags <= allowed_tags, 'Unknown image tag must be preserved/reconciled'
        remove = tags - ({record['tag']} if record['image_id'] == final else set())
        images.append(dict(id=record['image_id'], remove_tags=sorted(remove), keep=record['image_id'] == final))
    plan = dict(phase='validated_before_mutation', containers=containers, networks=networks,
                volumes=volumes, images=images, operations=sorted(operations))
    write(intent, plan)
    running = [row['id'] for row in containers if row['running']]
    if running:
        docker('stop', '-t', '10', *running)
    if containers:
        docker('rm', *(row['id'] for row in containers))
    docker('volume', 'rm', *volumes)
    docker('network', 'rm', *networks)
    for row in images:
        if row['remove_tags']:
            docker('image', 'rm', *row['remove_tags'])
        if not row['keep']:
            assert subprocess.run(['docker', 'image', 'inspect', row['id']], capture_output=True).returncode != 0
    for row in containers:
        assert subprocess.run(['docker', 'inspect', row['id']], capture_output=True).returncode != 0
    for name in volumes:
        assert subprocess.run(['docker', 'volume', 'inspect', name], capture_output=True).returncode != 0
    for name in networks:
        assert subprocess.run(['docker', 'network', 'inspect', name], capture_output=True).returncode != 0
    assert json.loads(docker('image', 'inspect', final))[0]['Id'] == final
    report = dict(plan, phase='retired_and_verified', utc=datetime.now(timezone.utc).isoformat(),
        removed_containers=len(containers), removed_volumes=len(volumes), removed_networks=len(networks),
        removed_images=sum(not row['keep'] for row in images),
        removed_image_tags=sum(len(row['remove_tags']) for row in images), retained_foundation_image=final,
        unrelated_assets_and_private_evidence_preserved=True)
    write(output, report)
    write(intent, dict(report))
    print(json.dumps({key: report[key] for key in ['phase', 'removed_containers', 'removed_volumes', 'removed_networks', 'removed_images', 'removed_image_tags']}))


if __name__ == '__main__':
    main()
