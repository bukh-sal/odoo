"""Seal a locally qualified kit; this grants no publisher or executor authority."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

from application_inputs import load_application_inputs
from verify import verify, digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit', type=Path)
    parser.add_argument('--decision', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--application-build', type=Path, required=True)
    parser.add_argument('--application-reproduction', type=Path, required=True)
    args = parser.parse_args()
    kit = args.kit.resolve()
    if not kit.is_relative_to(ROOT / '.local/releases') or args.receipt.exists():
        raise ValueError('Owned kit and fresh receipt required')
    old = verify(kit)
    if old['stage'] != 'draft_requires_clean_install_and_G7_closure':
        raise ValueError('Only an unsealed draft may be sealed')
    selected = load_application_inputs(ROOT, args.application_reproduction, args.application_build)
    decision = json.loads(args.decision.read_bytes())
    images = json.loads((kit / 'images.json').read_bytes())
    if (decision.get('result') != 'passed_consolidated_foundation_qualification'
            or decision.get('gates') != {f'CF-0{i}': 'passed' for i in range(1, 6)}
            or decision.get('checks') != {f'CF-{letter}': 'passed' for letter in 'ABCDEFGHIJKL'}
            or decision.get('image') != images['images']['application']['image_id']
            or decision['image'] != selected['build']['image_id']
            or decision.get('inventory_digest') != images['application_inventory_digest']):
        raise ValueError('Complete exact current release qualification required')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    if old['source_commit'] != head or subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=ROOT).returncode:
        raise ValueError('Refresh the clean committed source before sealing')
    evidence = decision.get('evidence')
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError('Actual source-archived evidence required')
    with zipfile.ZipFile(kit / 'source.zip') as archive:
        if archive.comment.decode() != head:
            raise ValueError('Source archive identity differs')
        for name, expected in evidence.items():
            path = PurePosixPath(name)
            if (not name.startswith('docs/evidence/') or path.is_absolute() or '..' in path.parts
                    or '\\' in name or path.as_posix() != name
                    or hashlib.sha256(archive.read(name)).hexdigest() != expected):
                raise ValueError('Qualification evidence differs from source archive')
    # All refusal paths above precede mutation. Checksums are packaging data,
    # not signatures, runtime approvals, or a production deployment claim.
    before = digest(kit / 'kit-inventory.json')
    name = 'qualification/foundation-release.json'
    target = kit / name
    with target.open('xb') as stream:
        stream.write(args.decision.read_bytes())
    updated = json.loads(json.dumps(old))
    updated['files'][name] = dict(bytes=target.stat().st_size, sha256=digest(target))
    updated.update(stage='qualified_local_foundation_cf_1', qualification=name)
    (kit / 'kit-inventory.json').write_text(json.dumps(updated, sort_keys=True, indent=2) + '\n', encoding='utf8')
    sums = {name: row['sha256'] for name, row in updated['files'].items()}
    sums['kit-inventory.json'] = digest(kit / 'kit-inventory.json')
    (kit / 'SHA256SUMS').write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(sums.items())), encoding='utf8')
    verify(kit)
    report = dict(result='sealed_verified_local_foundation', source_commit=head, image=decision['image'],
                  manifest_before=before, manifest_sha256=digest(kit / 'kit-inventory.json'),
                  decision_sha256=digest(target), components=len(updated['files']),
                  limits='Local CF qualification only; checksums do not authenticate publishers or authorize deployment.')
    with args.receipt.open('x', encoding='utf8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
