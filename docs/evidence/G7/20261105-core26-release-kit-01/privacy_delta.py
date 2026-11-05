"""Verify source identity and scan changed kit members against prior exact proofs."""
import base64
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path.cwd()
OUT = Path(__file__).parent
KIT = ROOT / '.local/releases/r1-0.1.26'
OLD_KIT = ROOT / '.local/releases/r1-0.1.23'
OLD_PROOF = OUT.parent / '20261104-release-kit-01'
OLD_SCAN = ROOT / '.local/g7-release-kit-privacy-01'
AFTER_REFRESH = sys.argv[1:] == ['--after-refresh']
assert AFTER_REFRESH or not sys.argv[1:]
RUN = 'final' if AFTER_REFRESH else 'streamed'
PRIVATE = ROOT / f'.local/g7-core26-kit-privacy-{RUN}'
sys.path[:0] = [str(ROOT / 'release'), str(ROOT / 'tools'), str(ROOT / 'packages/platform_sdk')]
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner, save_report
from verify import verify

LIMIT = 1024 ** 3


def load(path):
    return json.loads(path.read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, timeout=120)


assert not PRIVATE.exists()
protect_directory(PRIVATE)
current = verify(KIT)
previous = verify(OLD_KIT)
qualified = load(OLD_PROOF / 'kit-qualified.json')
assert file_sha(OLD_KIT / 'kit-inventory.json') == qualified['kit_manifest_sha256']
assert previous['source_commit'] == qualified['source_commit']
assert qualified['known_generated_findings'] == qualified['unreviewed_findings'] == 0
for name, digest in qualified['proof_sha256'].items():
    assert file_sha(OLD_PROOF / name) == digest
prior_bytes = set()
for inventory, proof in [('inventory.json', 'kit-expanded-privacy.json'),
                         ('nested-inventory.json', 'kit-nested-privacy.json')]:
    path = OLD_SCAN / inventory
    assert file_sha(path) == load(OLD_PROOF / proof)['inventory_sha256']
    prior_bytes.update(row['sha256'] for row in load(path)
                       if not row['location'].startswith('git-history'))

known_path = ROOT / '.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json'
known = {name: base64.b64decode(value) for name, value in load(known_path).items()}
assert len(known) == qualified['known_values'] == 133
scanner = Scanner((ROOT / '.local/g5-secret-scan/fingerprint-key').read_bytes(), known)
patterns = PRIVATE / 'patterns.regex'
scanner.write_patterns(patterns)
# Match the exact known-byte variants and generic rules from the previous scan.
new_patterns = patterns.read_bytes().splitlines()
old_patterns = (OLD_SCAN / 'all-values.regex').read_bytes().splitlines()
assert set(new_patterns[0].split(b'|')) == set(old_patterns[0].split(b'|'))
assert new_patterns[1:] == old_patterns[1:]
unchanged = sorted(name for name, row in current['files'].items()
                   if previous['files'].get(name) == row)
changed = sorted(set(current['files']) - set(unchanged))
assert {'source.zip', 'images.tar'} <= set(changed)
findings = scanner.scan_paths([KIT / name for name in changed + ['kit-inventory.json', 'SHA256SUMS']],
                              patterns, root=KIT)
counts = Counter()
seen = set()


def walk_tar(archive, location, depth):
    for row in archive:
        header = json.dumps([row.name, row.linkname, row.pax_headers]).encode()
        visit(header, location + '/header/' + row.name, depth + 1)
        if row.isfile():
            assert row.size <= LIMIT
            visit(archive.extractfile(row).read(), location + '/' + row.name, depth + 1)


def visit(raw, location, depth=0):
    assert depth <= 8 and len(raw) <= LIMIT, location
    digest = sha(raw)
    if digest in seen:
        counts['duplicate'] += 1
        return
    if digest in prior_bytes:
        counts['previous_bytes'] += 1
        return
    seen.add(digest)
    counts['new_bytes'] += 1
    findings.extend(scanner.inspect_bytes(raw, location))
    if zipfile.is_zipfile(io.BytesIO(raw)):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows = archive.infolist()
            assert len(rows) <= 100_000 and sum(row.file_size for row in rows) <= LIMIT
            assert len({row.filename for row in rows}) == len(rows)
            for row in rows:
                if not row.is_dir():
                    assert not row.flag_bits & 1
                    visit(archive.read(row), location + '/' + row.filename, depth + 1)
    elif raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            data = handle.read(LIMIT + 1)
        visit(data, location + '/gzip-content', depth + 1)
    elif raw[257:262] == b'ustar':
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
            walk_tar(archive, location, depth)


tree = {}
head = current['source_commit']
for entry in git('ls-tree', '-rz', '--full-tree', head).split(b'\0'):
    if entry:
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        assert kind == 'blob' and mode in {'100644', '100755'}
        tree[name.decode()] = oid
observed = set()
with zipfile.ZipFile(KIT / 'source.zip') as archive:
    assert archive.comment.decode() == head
    assert sum(row.file_size for row in archive.infolist()) <= 2 * LIMIT
    for row in archive.infolist():
        if row.is_dir():
            continue
        assert row.filename not in observed and not row.filename.startswith(('.git/', '.local/'))
        raw = archive.read(row)
        oid = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        assert tree[row.filename] == oid
        observed.add(row.filename)
        visit(raw, 'source/' + row.filename)
assert observed == set(tree)
print(json.dumps({'phase': 'source_verified', 'files': len(observed), 'findings': len(findings)}), flush=True)

with tarfile.open(OLD_KIT / 'images.tar') as archive:
    prior_blobs = {row.name for row in archive if row.isfile() and row.name.startswith('blobs/sha256/')}
with tarfile.open(KIT / 'images.tar') as archive:
    index = json.load(archive.extractfile('index.json'))
    assert {row['digest'] for row in index['manifests']} == {row['image_id'] for row in current['images'].values()}
    names = set()
    for row in archive:
        assert row.name not in names
        names.add(row.name)
        if not row.isfile():
            continue
        assert row.size <= LIMIT
        raw = archive.extractfile(row).read()
        if row.name.startswith('blobs/sha256/'):
            assert sha(raw) == row.name.rsplit('/', 1)[1]
            if row.name in prior_blobs:
                counts['previous_verified_image_blob'] += 1
                continue
            try:
                layer = tarfile.open(fileobj=io.BytesIO(raw), mode='r:*')
            except tarfile.ReadError:
                pass
            else:
                with layer:
                    walk_tar(layer, 'images/' + row.name, 0)
                counts['new_image_layers_expanded'] += 1
                continue
        visit(raw, 'images/' + row.name)
for name in changed:
    if name not in {'source.zip', 'images.tar'}:
        visit((KIT / name).read_bytes(), 'component/' + name)
print(json.dumps({'phase': 'image_and_component_delta', 'counts': counts, 'findings': len(findings)}), flush=True)

# History is traversed from the prior qualified head through the actual kit head.
old_head = previous['source_commit']
subprocess.run(['git', 'merge-base', '--is-ancestor', old_head, head], check=True, timeout=30)
objects = git('rev-list', '--objects', '--no-object-names', old_head + '..' + head).decode().splitlines()
typed = subprocess.check_output(['git', 'cat-file', '--batch-check'], input=('\n'.join(objects) + '\n').encode(),
                                timeout=60).decode().splitlines()
assert len(typed) == len(objects)
for line in typed:
    oid, kind, size = line.split()
    if kind == 'blob':
        assert int(size) <= LIMIT
        visit(git('cat-file', 'blob', oid), 'history/' + oid)
        counts['history_blobs'] += 1

report = {
    'result': 'passed_exact_prior_proof_and_expanded_kit_delta' if not findings else 'triage_required',
    'utc': datetime.now(timezone.utc).isoformat(), 'kit_manifest_sha256': file_sha(KIT / 'kit-inventory.json'),
    'previous_manifest_sha256': qualified['kit_manifest_sha256'], 'source_commit': head,
    'previous_source_commit': old_head, 'source_files_exact_to_git': len(tree),
    'unchanged_components': unchanged, 'changed_components': changed,
    'known_values': len(known), 'counts': counts, 'findings': findings,
    'prior_scan_attempt': 'Stopped owned read-only process after 419 CPU seconds. Source identity had passed. The first implementation rescanned compressed layers and whole expanded tar buffers.',
    'scope': 'Exact previous audited bytes plus current transport, ZIP, TAR, gzip and Git delta. Bounded detector scope.',
}
save_report(OUT / ('privacy-delta-final.json' if AFTER_REFRESH else 'privacy-delta.json'), report)
print(json.dumps({key: report[key] for key in ('result', 'source_files_exact_to_git', 'counts')}))
assert not findings, 'Review redacted finding records before any release claim'
