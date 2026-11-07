"""Finite known-value audit of kit archives and new application filesystem layers."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / '.local/releases/foundation-r1-core46'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--source-only', type=Path, help='Passed prior full receipt; unchanged image archive required')
    args = parser.parse_args()
    assert not args.receipt.exists()
    accounts = [ROOT / '.local/foundation-release/cf-01' / key / 'account-passwords.json'
                for key in ('aurora', 'maintenance')]
    accounts += [ROOT / '.local/foundation-release/clean-core46/private/reference/account-passwords.json']
    values = set()
    for path in accounts:
        values.update(value for value in json.loads(path.read_bytes()).values() if len(value) >= 16)
    patterns = set()
    for value in values:
        raw = value.encode()
        patterns.update((raw, value.encode('utf-16le'), base64.b64encode(raw), base64.urlsafe_b64encode(raw)))
    match = re.compile(b'|'.join(re.escape(value) for value in sorted(patterns)))
    seen, findings = set(), []
    totals = dict(files=0, unique_contents=0, bytes=0, archives=0)
    def scan(data, label, depth=0):
        assert depth <= 5 and len(data) <= 128 * 1024 * 1024, 'Explicit archive bounds exceeded'
        totals['files'] += 1
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            return
        seen.add(digest)
        totals['unique_contents'] += 1
        totals['bytes'] += len(data)
        if match.search(data):
            findings.append(dict(path=label, content_sha256=digest))
        if data.startswith(b'PK\x03\x04'):
            totals['archives'] += 1
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for row in archive.infolist():
                    if not row.is_dir():
                        assert row.file_size <= 128 * 1024 * 1024
                        scan(archive.read(row), label + '!' + row.filename, depth + 1)
    manifest = json.loads((KIT / 'kit-inventory.json').read_bytes())
    for name in manifest['files']:
        if name == 'images.tar':
            continue
        path = KIT / name
        if name == 'source.zip':
            totals['archives'] += 1
            with zipfile.ZipFile(path) as archive:
                for row in archive.infolist():
                    if not row.is_dir():
                        assert row.file_size <= 128 * 1024 * 1024
                        scan(archive.read(row), name + '!' + row.filename)
        else:
            scan(path.read_bytes(), name)
    images = json.loads((KIT / 'images.json').read_bytes())['images']
    digest = lambda path: hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    image_archive_sha = digest(KIT / 'images.tar')
    layers_scanned = []
    if args.source_only:
        old = json.loads(args.source_only.read_bytes())
        assert old['result'] == 'passed_finite_known_values' and old['images_tar_sha256'] == image_archive_sha
        assert old['image'] == images['application']['image_id']
    else:
        application, = json.loads(subprocess.check_output(['docker', 'image', 'inspect', images['application']['image_id']]))
        dependency, = json.loads(subprocess.check_output(['docker', 'image', 'inspect', images['dependency_base']['image_id']]))
        app_layers, base_layers = application['RootFS']['Layers'], dependency['RootFS']['Layers']
        assert app_layers[:len(base_layers)] == base_layers
        scan(json.dumps(application, sort_keys=True).encode(), 'application-image-metadata')
        with tarfile.open(KIT / 'images.tar', 'r:*') as outer:
            index = json.load(outer.extractfile('manifest.json'))
            selected = []
            for row in index:
                config = json.load(outer.extractfile(row['Config']))
                if config['rootfs']['diff_ids'] == app_layers:
                    selected.append(row)
            selected, = selected
            assert len(selected['Layers']) == len(app_layers)
            for name in selected['Layers'][len(base_layers):]:
                with tarfile.open(fileobj=outer.extractfile(name), mode='r|*') as layer:
                    for row in layer:
                        if row.isfile():
                            assert row.size <= 128 * 1024 * 1024
                            scan(layer.extractfile(row).read(), 'new-layer:' + name + '!' + row.name)
                layers_scanned.append(name)
    report = dict(result='failed_known_value' if findings else 'passed_finite_known_values',
        image=images['application']['image_id'], kit_source=manifest['source_commit'],
        kit_manifest_sha256=digest(KIT / 'kit-inventory.json'), images_tar_sha256=image_archive_sha,
        known_values=len(values), encodings=len(patterns), totals=totals, findings=findings,
        new_application_layers=layers_scanned, prior_full_receipt=str(args.source_only) if args.source_only else None,
        limits=['Known current CF credentials only; no unknown-secret detector or publisher authentication claim.',
                'Unchanged dependency/support image bytes retain the recorded stock release audit scope.',
                'Source ZIP, curated archives and new application layers decoded; nested ZIP depth <=5, files <=128MiB.'])
    args.receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(result=report['result'], totals=totals, known_values=len(values), findings=len(findings))))
    assert not findings


if __name__ == '__main__':
    main()
