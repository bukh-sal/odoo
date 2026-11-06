"""Verify diagnostic streams against the actual disposable stock credentials."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from secret_scan import Scanner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', choices=('clean', 'clean-02', 'clean-rtl', 'clean-final', 'clean-stock'))
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    site = ROOT / '.local/stock-webclient-release' / args.work / 'private/reference'
    state = json.loads((site / 'state.json').read_bytes())
    credentials = {name: value.encode() for name, value in json.loads((site / 'account-passwords.json').read_bytes()).items()}
    credentials['worker_issuer'] = (site / 'worker/issuer.pem').read_bytes()
    scanner = Scanner((ROOT / '.local/g5-secret-scan/fingerprint-key').read_bytes(), credentials)
    files = sorted((site / 'logs').iterdir())
    control = site / 'operator/control'
    for glob in ('stages/**/*.stdout', 'stages/**/*.stderr', 'stages/**/*.log'):
        files.extend(control.glob(glob))
    assert files
    findings = []
    for file in files:
        assert file.is_file() and file.stat().st_size < 100 * 1024 * 1024
        findings.extend(scanner.inspect_file(file, file.relative_to(site).as_posix()))
    docker = ['docker', 'ps', '-aq', '--filter', 'name=' + state['project'].removeprefix('mp-r0-r1release')]
    ids = subprocess.check_output(docker, timeout=30).decode().split()
    assert ids
    count = 0
    for container in json.loads(subprocess.check_output(['docker', 'inspect', *ids], timeout=30)):
        if container['HostConfig']['LogConfig']['Type'] != 'none':
            result = subprocess.run(['docker', 'logs', container['Id']], capture_output=True, check=True, timeout=30)
            findings.extend(scanner.inspect_bytes(result.stdout + result.stderr, container['Name']))
            count += 1
    receipt = {'result': 'passed' if not findings else 'triage_required',
               'reference_project': state['project'], 'generated_values': len(credentials),
               'private_diagnostic_streams': len(files), 'docker_log_streams': count, 'findings': findings}
    with args.receipt.open('x', encoding='utf-8') as output:
        json.dump(receipt, output, indent=2)
        output.write('\n')
    assert not findings, 'Inspect the redacted result before releasing'
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
