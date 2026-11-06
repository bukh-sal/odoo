"""Remove only superseded or temporary image tags from the stock qualification."""

import argparse
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / 'docs/evidence/G7'
OWNED = ROOT / '.local/stock-webclient-release'


def load(path):
    return json.loads(path.read_bytes())


def docker(*args):
    return subprocess.run(['docker', *args], check=False, capture_output=True, text=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    assert not args.receipt.exists()
    selected = load(EVIDENCE / '20261105-stock-release-repro/qualification.json')
    previous = load(EVIDENCE / '20261105-stock-final-repro/qualification.json')
    tags = {
        'modular-platform:stock-rtl-input-core26': 'sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415',
        'modular-platform:stock-rtl-dependencies-01': previous['dependency_base'],
        'modular-platform:stock-rtl-dependencies-02': previous['independently_rebuilt_rtl_base'],
        'modular-platform:stock-rtl-bounded-02': selected['independently_rebuilt_rtl_base'],
    }
    for folder in ('20261105-stock-kit-build-01', '20261105-stock-kit-repro-01',
                   '20261105-stock-kit-build-02', '20261105-stock-kit-repro-02',
                   '20261105-stock-rtl-build-01', '20261105-stock-rtl-repro-01',
                   '20261105-stock-final-build', '20261105-stock-final-repro', '20261105-stock-bounded-build',
                   '20261105-stock-bounded-repro', '20261105-stock-release-repro'):
        build = load(EVIDENCE / folder / 'candidate-build.json')
        assert re.fullmatch(r'modular-platform:stage-[0-9a-z]+', build['tag'])
        tags[build['tag']] = build['image_id']
    for work in ('clean', 'clean-02', 'clean-rtl', 'clean-final', 'clean-stock'):
        site = OWNED / work / 'private/reference'
        state = load(site / 'state.json')
        nonce = re.fullmatch(r'mp-r0-r1release([0-9a-f]{12})', state['project']).group(1)
        containers = docker('ps', '-aq', '--filter', 'name=' + nonce)
        assert containers.returncode == 0 and not containers.stdout.strip()
        for path in (site / 'operator/control/checkpoints').glob('*/manifest.json'):
            checkpoint = load(path)
            assert checkpoint['configuration']['project'] == state['project']
            assert re.fullmatch(r'[a-f0-9-]{36}', checkpoint['operation_id'])
            tags['modular-platform:retained-' + checkpoint['operation_id']] = checkpoint['configuration']['image_id']
    results = {}
    for tag, expected in tags.items():
        image = docker('image', 'inspect', tag, '--format', '{{.Id}}')
        if image.returncode:
            results[tag] = 'already absent'
            continue
        assert image.stdout.strip() == expected
        result = docker('image', 'rm', tag)
        results[tag] = 'retired' if result.returncode == 0 else 'retained by Docker reference'
    for key in ('reference_image', 'dependency_base'):
        assert docker('image', 'inspect', selected[key], '--format', '{{.Id}}').stdout.strip() == selected[key]
    with args.receipt.open('x', encoding='utf-8') as output:
        json.dump(dict(tags=results, selected_image=selected['reference_image'],
                       selected_dependency=selected['dependency_base']), output, indent=2)
        output.write('\n')
    print(json.dumps({'retired': list(results.values()).count('retired'), 'reviewed': len(results)}))


if __name__ == '__main__':
    main()
