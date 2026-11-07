"""Retire one recorded disposable AR profile; never baseline or global assets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    return subprocess.check_output(['docker', *args], timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    parser.add_argument('profile')
    args = parser.parse_args()
    assert all(re.fullmatch('[a-z0-9-]+', value) for value in (args.run, args.profile))
    local = (ROOT / '.local/addon-cleanup/profiles' / args.run / args.profile).resolve()
    assert local.is_relative_to(ROOT / '.local/addon-cleanup/profiles')
    state = json.loads((local / 'state.json').read_bytes())
    project = state['project']
    assert re.fullmatch('mp-r0-r1release[a-f0-9]{12}', project)
    assert state['database'] == 'mp_disposable_r0_r1_release_' + project[-12:]
    receipt = local / 'retirement.json'
    assert not receipt.exists(), 'Inspect any partial retirement before proceeding'
    names = docker('ps', '-a', '--format', '{{.Names}}').decode().splitlines()
    selected = [name for name in names if name.startswith(project + '-')]
    rows = json.loads(docker('inspect', *selected)) if selected else []
    for row in rows:
        labels = row['Config']['Labels'] or {}
        assert (labels.get('com.docker.compose.project') == project
                or labels.get('com.modular.disposable') == project
                or labels.get('com.modular.deployment') == state['deployment_id'])
    resources = state['owned_resources']
    for kind, key in (('volume', 'volumes'), ('network', 'networks')):
        for row in json.loads(docker(kind, 'inspect', *resources[key])):
            assert row['Labels'].get('com.modular.disposable') == project
    record = dict(phase='verified_exact_owned_resources', project=project,
                  containers=[row['Id'] for row in rows], volumes=resources['volumes'],
                  networks=resources['networks'], utc=datetime.now(timezone.utc).isoformat(),
                  source_phase=state['phase'], private_diagnostics_preserved=True)
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    if rows:
        docker('rm', '-fv', *record['containers'])
    docker('volume', 'rm', *record['volumes'])
    docker('network', 'rm', *record['networks'])
    assert not any(name.startswith(project + '-') for name in docker('ps', '-a', '--format', '{{.Names}}').decode().splitlines())
    record['phase'] = 'retired'
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(result='retired_exact_disposable_profile', project=project,
                         containers=len(rows), volumes=len(record['volumes']), networks=len(record['networks']))))


if __name__ == '__main__':
    main()
