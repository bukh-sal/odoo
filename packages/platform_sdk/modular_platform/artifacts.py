"""R1 data-only archive inspection. This module never imports package code.

The portable ZIP profile intentionally excludes ZIP64, encryption, extra fields,
comments, data descriptors and executable deployment formats. Native Python and
same-origin JavaScript remain trusted code after independent operator approval.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import tomllib
import unicodedata
import zipfile
import zlib

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .contracts import ContractError, load_json, native_version, normalize_manifest


class ArtifactError(ContractError):
    """Safe validation error; never includes source text or detected secrets."""


@dataclass(frozen=True)
class ArchiveLimits:
    compressed: int = 100 * 1024 * 1024
    expanded: int = 500 * 1024 * 1024
    entries: int = 10_000
    per_file: int = 64 * 1024 * 1024
    ratio: int = 200
    metadata: int = 4 * 1024 * 1024

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in vars(self).values()):
            raise ArtifactError('Archive limits must be positive operator-configured integers')


@dataclass(frozen=True)
class TrustPolicy:
    mode: str = 'curated'
    approved_digests: frozenset[str] = field(default_factory=frozenset)
    allow_unsigned_development: bool = False
    generation: int = 1

    def check(self, digest):
        if type(self.generation) is not int or self.generation < 1:
            raise ArtifactError('Invalid trust policy generation')
        if self.mode == 'curated' and digest in self.approved_digests:
            return {'model': 'operator-approved-exact-digest', 'signature_verified': False,
                    'policy_generation': self.generation, 'warnings': []}
        if self.mode == 'development' and self.allow_unsigned_development is True:
            return {'model': 'unsigned-development', 'signature_verified': False,
                    'policy_generation': self.generation,
                    'warnings': ['UNSIGNED DEVELOPMENT ARTIFACT: native and frontend code is fully trusted.']}
        raise ArtifactError('Artifact is not approved by the independently configured trust policy')


def portable_path(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > 1024:
        raise ArtifactError('Invalid portable archive path')
    if unicodedata.normalize('NFC', value) != value:
        raise ArtifactError('Noncanonical Unicode archive path')
    if any(ord(char) < 32 or ord(char) == 127 or char in '\\:<>"|?*' for char in value):
        raise ArtifactError('Unsafe portable archive path')
    parts = value.split('/')
    if any(part in ('', '.', '..') or part.endswith((' ', '.')) or len(part.encode('utf-8')) > 240 for part in parts):
        raise ArtifactError('Unsafe portable archive path')
    for part in parts:
        if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', part.split('.')[0], re.I):
            raise ArtifactError('Reserved portable archive path')
    return value


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _zip_preflight(stream, size, limits):
    # Bound central-directory allocation BEFORE ZipFile constructs ZipInfo objects.
    # This is a strict subset of the standard ZIP format, not an alternate extractor.
    if size < 22 or size > limits.compressed:
        raise ArtifactError('Compressed archive size limit')
    stream.seek(size - 22)
    end = struct.unpack('<4s4H2LH', stream.read(22))
    signature, disk, start_disk, local_count, count, cd_size, cd_offset, comment = end
    if signature != b'PK\x05\x06' or disk or start_disk or local_count != count or comment:
        raise ArtifactError('Unsupported ZIP footer, multipart archive or comment')
    if not 1 <= count <= min(limits.entries, 65534):
        raise ArtifactError('Archive entry count limit')
    if cd_offset + cd_size != size - 22 or cd_size > count * (46 + 1024):
        raise ArtifactError('Invalid or excessive ZIP central directory')
    stream.seek(cd_offset)
    cursor = cd_offset
    for _ in range(count):
        raw = stream.read(46)
        if len(raw) != 46:
            raise ArtifactError('Truncated ZIP directory')
        record = struct.unpack('<4s4B4HL2L5H2L', raw)
        name_size, extra_size, comment_size = record[12:15]
        if record[0] != b'PK\x01\x02' or not 1 <= name_size <= 1024 or extra_size or comment_size or record[15]:
            raise ArtifactError('Unsupported ZIP directory metadata')
        cursor += 46 + name_size
        if cursor > cd_offset + cd_size:
            raise ArtifactError('Truncated ZIP directory')
        stream.seek(name_size, 1)
    if cursor != cd_offset + cd_size:
        raise ArtifactError('ZIP directory entry count mismatch')
    return count, cd_offset


_SECRET = re.compile(
    rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'
    rb'|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}'
    rb'|\b(?:password|api_key|client_secret|access_token)\s*[=:]\s*[\"\x27][^\"\x27\r\n]{8,}[\"\x27]', re.I)
_REMOTE_CODE = re.compile(
    rb'<script\b[^>]*\bsrc\s*=\s*[\"\x27]\s*(?:https?:)?//'
    rb'|\b(?:import|export)\s+(?:[^;\r\n]{0,200}?\s+from\s*)?[\"\x27](?:https?:)?//'
    rb'|\bimport\s*\(\s*[\"\x27](?:https?:)?//'
    rb'|\b(?:importScripts|Worker|SharedWorker)\s*\(\s*[\"\x27](?:https?:)?//', re.I)


def _lint(data, name):
    if _SECRET.search(data):
        raise ArtifactError('Supplementary secret lint rejected package content')
    if name.startswith('frontend/') or '/static/' in name:
        if _REMOTE_CODE.search(data) or re.search(rb'https?://[^\s/]+:[^\s/]+@', data, re.I):
            raise ArtifactError('Unapproved remote browser code or embedded URL credentials')


@dataclass(frozen=True)
class VerifiedArtifact:
    digest: str
    manifest: dict
    inventory: dict[str, str]
    provenance: dict
    trust: dict
    size: int
    expanded_size: int
    native_manifest: dict | None

    def descriptor(self):
        return {'plugin_id': self.manifest['plugin']['id'], 'version': self.manifest['plugin']['version'],
                'digest': self.digest, 'runtime_kind': self.manifest['runtime']['kind'],
                'manifest': self.manifest, 'inventory': self.inventory, 'provenance': self.provenance,
                'trust': self.trust, 'size': self.size, 'expanded_size': self.expanded_size,
                'native_manifest': self.native_manifest}


class ArtifactValidator:
    def __init__(self, policy: TrustPolicy, limits: ArchiveLimits | None = None):
        self.policy, self.limits = policy, limits or ArchiveLimits()

    def verify(self, source, *, expected_digest=None):
        try:
            with Path(source).open('rb') as stream:
                return self._verify(stream, expected_digest)
        except ArtifactError:
            raise
        except (OSError, ValueError, RuntimeError, EOFError, struct.error, zipfile.BadZipFile,
                RecursionError, SyntaxError, UnicodeError, SchemaError, zlib.error, TypeError) as error:
            raise ArtifactError('Invalid or unreadable artifact') from error

    def _verify(self, stream, expected_digest):
        before = os.fstat(stream.fileno())
        count, cd_offset = _zip_preflight(stream, before.st_size, self.limits)
        stream.seek(0)
        outer_hash, hashed_size = hashlib.sha256(), 0
        while chunk := stream.read(64 * 1024):
            hashed_size += len(chunk)
            if hashed_size > self.limits.compressed:
                raise ArtifactError('Actual compressed archive size limit')
            outer_hash.update(chunk)
        if hashed_size != before.st_size:
            raise ArtifactError('Artifact changed during hashing')
        digest = 'sha256:' + outer_hash.hexdigest()
        if expected_digest is not None and digest != expected_digest:
            raise ArtifactError('Outer artifact digest mismatch')
        trust = self.policy.check(digest)
        hashes, metadata, seen, roots = {}, {}, {}, set()
        total, cursor = 0, 0
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            if len(infos) != count:
                raise ArtifactError('ZIP entry count mismatch')
            for entry in sorted(infos, key=lambda info: info.header_offset):
                directory = entry.is_dir()
                name = entry.filename[:-1] if directory else entry.filename
                if entry.orig_filename != entry.filename:
                    raise ArtifactError('Truncated ZIP filename')
                portable_path(name)
                key = name.casefold()
                if key in seen:
                    raise ArtifactError('Duplicate or case-insensitive archive path collision')
                seen[key] = directory
                roots.add(name.split('/')[0])
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if mode not in (0, stat.S_IFDIR if directory else stat.S_IFREG):
                    raise ArtifactError('Links and special archive entries are forbidden')
                if entry.create_system not in (0, 3) or (entry.external_attr & 0x10 and not directory):
                    raise ArtifactError('Unsupported archive entry attributes')
                if entry.extra or entry.comment or entry.flag_bits & ~0x800 or entry.compress_type not in (0, 8):
                    raise ArtifactError('Unsupported ZIP flags, compression or metadata')
                if entry.header_offset != cursor:
                    raise ArtifactError('Overlapping, prefixed or unindexed ZIP data')
                stream.seek(cursor)
                header = stream.read(30)
                if len(header) != 30:
                    raise ArtifactError('Truncated local ZIP header')
                local = struct.unpack('<4s5H3L2H', header)
                if (local[0] != b'PK\x03\x04' or local[2] != entry.flag_bits or local[3] != entry.compress_type
                        or local[6:9] != (entry.CRC, entry.compress_size, entry.file_size)
                        or local[10] or not 1 <= local[9] <= 1024):
                    raise ArtifactError('Inconsistent or unsupported local ZIP header')
                cursor += 30 + local[9] + entry.compress_size
                if cursor > cd_offset or entry.file_size > self.limits.per_file:
                    raise ArtifactError('Per-file expanded size limit')
                if entry.file_size > max(1, entry.compress_size) * self.limits.ratio:
                    raise ArtifactError('Compression ratio limit')
                if directory:
                    if entry.file_size or entry.compress_size:
                        raise ArtifactError('Directory entries must be empty')
                    continue
                if '/' not in name:
                    raise ArtifactError('Every file must be under one package root')
                relative = name.split('/', 1)[1]
                capture = relative in ('plugin.toml', 'inventory.json', 'provenance.json') or relative.startswith('schemas/') or relative.endswith('/__manifest__.py')
                chunks, file_hash, actual, tail = [], hashlib.sha256(), 0, b''
                with archive.open(entry) as content:
                    while chunk := content.read(64 * 1024):
                        actual += len(chunk)
                        total += len(chunk)
                        if actual > self.limits.per_file or total > self.limits.expanded:
                            raise ArtifactError('Actual expanded size limit')
                        if actual > max(1, entry.compress_size) * self.limits.ratio:
                            raise ArtifactError('Actual compression ratio limit')
                        file_hash.update(chunk)
                        _lint(tail + chunk, relative)
                        tail = chunk[-1024:]
                        if capture:
                            if actual > self.limits.metadata:
                                raise ArtifactError('Metadata size limit')
                            chunks.append(chunk)
                if actual != entry.file_size:
                    raise ArtifactError('Actual archive entry size mismatch')
                hashes[relative] = file_hash.hexdigest()
                if capture:
                    metadata[relative] = b''.join(chunks)
        if cursor != cd_offset or len(roots) != 1:
            raise ArtifactError('Archive must contain exactly one indexed package root')
        for key in seen:
            parent = key
            while '/' in parent:
                parent = parent.rsplit('/', 1)[0]
                if parent in seen and not seen[parent]:
                    raise ArtifactError('Archive file/directory prefix collision')
        if not {'plugin.toml', 'inventory.json', 'provenance.json'} <= metadata.keys():
            raise ArtifactError('Missing manifest, inventory or provenance')
        manifest = normalize_manifest(tomllib.loads(metadata['plugin.toml'].decode('utf-8')))
        if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', manifest['plugin']['id']):
            raise ArtifactError('Invalid canonical plugin identifier')
        if roots != {manifest['plugin']['id']}:
            raise ArtifactError('Archive root must equal plugin identifier')
        inventory = load_json(metadata['inventory.json'])
        if not isinstance(inventory, dict) or set(inventory) != {'schema_version', 'files', 'excluded'} or type(inventory['schema_version']) is not int or inventory['schema_version'] != 1 or inventory['excluded'] != ['inventory.json']:
            raise ArtifactError('Unsupported inventory profile or self-hash exclusions')
        expected = {name: value for name, value in hashes.items() if name != 'inventory.json'}
        if inventory['files'] != expected or not all(_sha(value) for value in expected.values()):
            raise ArtifactError('Actual file hashes differ from declared inventory')
        provenance = load_json(metadata['provenance.json'])
        required = {'schema_version', 'builder', 'source_files'}
        allowed = required | {'trusted_inputs_only', 'upstream_commit'}
        if not isinstance(provenance, dict) or not required <= provenance.keys() or not provenance.keys() <= allowed or type(provenance['schema_version']) is not int or provenance['schema_version'] != 1 or not isinstance(provenance['builder'], str) or not 1 <= len(provenance['builder']) <= 200:
            raise ArtifactError('Invalid provenance profile')
        sources = {name: value for name, value in expected.items() if name != 'provenance.json'}
        if provenance['source_files'] != sources:
            raise ArtifactError('Provenance source inventory mismatch')
        native_manifest = self._layout(manifest, hashes, metadata)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ArtifactError('Artifact changed during inspection')
        return VerifiedArtifact(digest, manifest, hashes, provenance, trust, before.st_size, total, native_manifest)

    def _layout(self, manifest, hashes, metadata):
        native = manifest['runtime']['kind'] == 'native'
        addon = manifest['runtime'].get('addon_name')
        prefix = 'backend/odoo_addons/' + addon + '/' if native else None
        for name in hashes:
            if name in ('plugin.toml', 'inventory.json', 'provenance.json'):
                continue
            allowed = ('schemas/', 'notices/') + ((prefix, 'frontend/dist/', 'locales/') if native else ())
            if not name.startswith(allowed):
                raise ArtifactError('Payload outside the declared runtime layout')
            if not native and (name.startswith('schemas/') and not name.endswith('.json')):
                raise ArtifactError('External service schemas must be JSON data')
            if not native and name.startswith('notices/'):
                base = name.rsplit('/', 1)[-1]
                if base not in ('LICENSE', 'COPYRIGHT', 'NOTICE', 'AUTHORS') and not base.endswith(('.txt', '.md', '.rst')):
                    raise ArtifactError('External notices must be non-executable text documents')
        referenced = {item['schema'] for item in manifest['services']['provides']}
        referenced.update(item['context_schema'] for item in manifest['ui'].get('slots', []))
        referenced.update(item['input_schema'] for item in manifest['ui'].get('commands', []))
        if manifest['data'].get('export_schema'):
            referenced.add(manifest['data']['export_schema'])
        for name in referenced:
            portable_path(name)
            if not name.startswith('schemas/') or name not in metadata:
                raise ArtifactError('Missing declared JSON contract schema')
        for name, raw in metadata.items():
            if not name.startswith('schemas/'):
                continue
            schema = load_json(raw)
            Draft202012Validator.check_schema(schema)
            self._local_refs(schema)
        for page in manifest['ui']['pages']:
            if 'entry_asset' in page and (not page['entry_asset'].startswith('frontend/dist/') or page['entry_asset'] not in hashes):
                raise ArtifactError('Missing prebuilt page asset')
        if native:
            name = prefix + '__manifest__.py'
            if name not in metadata or prefix + '__init__.py' not in hashes:
                raise ArtifactError('Missing native addon entry points')
            native_manifest = ast.literal_eval(metadata[name].decode('utf-8'))
            allowed = {'name', 'version', 'depends', 'license', 'author', 'description', 'summary',
                       'category', 'website', 'data', 'demo', 'assets', 'installable', 'application',
                       'auto_install', 'sequence', 'maintainer', 'support', 'images'}
            if not isinstance(native_manifest, dict) or not native_manifest.keys() <= allowed:
                raise ArtifactError('Unrecognized native manifest keys or executable hooks')
            if native_manifest.get('version') != native_version(manifest['plugin']['version']):
                raise ArtifactError('Native and package versions disagree')
            if native_manifest.get('auto_install', False) is not False or native_manifest.get('installable', True) is not True:
                raise ArtifactError('Implicit native activation is forbidden')
            depends = native_manifest.get('depends')
            if not isinstance(depends, list) or not all(isinstance(value, str) and re.fullmatch('[a-z][a-z0-9_]*', value) for value in depends) or len(depends) != len(set(depends)):
                raise ArtifactError('Invalid native dependency declaration')
            license_map = {'LGPL-3.0-only': 'LGPL-3', 'GPL-3.0-only': 'GPL-3',
                           'AGPL-3.0-only': 'AGPL-3', 'MIT': 'Other OSI approved licence',
                           'Apache-2.0': 'Other OSI approved licence', 'BSD-3-Clause': 'Other OSI approved licence'}
            if manifest['plugin']['license'] not in license_map or license_map[manifest['plugin']['license']] != native_manifest.get('license'):
                raise ArtifactError('Native license must match an explicitly supported package license mapping')
            for field in ('data', 'demo', 'images'):
                values = native_manifest.get(field, [])
                if not isinstance(values, list):
                    raise ArtifactError('Invalid native data declaration')
                for value in values:
                    portable_path(value)
                    if prefix + value not in hashes:
                        raise ArtifactError('Missing declared native data file')
            declared_migrations = set()
            for transition in manifest['upgrade']['transitions']:
                for script in transition['scripts']:
                    declared_migrations.add(prefix + script['path'])
                    if 'sha256:' + hashes.get(prefix + script['path'], '') != script['digest']:
                        raise ArtifactError('Declared migration script digest mismatch')
            if {name for name in hashes if name.startswith(prefix + 'migrations/')} != declared_migrations:
                raise ArtifactError('Undeclared or noncanonical native migration payload')
            # Asset ownership/dependency mapping is also checked against the resolved
            # release by the planner; unknown imperative native hooks never run here.
            assets = native_manifest.get('assets', {})
            if not isinstance(assets, dict):
                raise ArtifactError('Invalid native assets declaration')
            for bundle, values in assets.items():
                if not isinstance(bundle, str) or not isinstance(values, list):
                    raise ArtifactError('Invalid native assets declaration')
                for value in values:
                    if not isinstance(value, str) or not value.startswith(addon + '/'):
                        raise ArtifactError('R1 plugin assets must be explicit owned files')
                    portable_path(value)
                    if prefix + value[len(addon) + 1:] not in hashes:
                        raise ArtifactError('Missing declared native asset')
            return native_manifest
        return None

    @staticmethod
    def _local_refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('$ref', '$dynamicRef') and (not isinstance(child, str) or not child.startswith('#')):
                    raise ArtifactError('Remote schema references are forbidden')
                ArtifactValidator._local_refs(child)
        elif isinstance(value, list):
            for child in value:
                ArtifactValidator._local_refs(child)

    def stage(self, source, parent, *, expected_digest):
        """Return a private TemporaryDirectory; caller owns its context/lifetime.

        Copy first to defeat replacement of an uploaded path; inspect and extract
        only that private copy, using exclusive creation and actual written hashes.
        Parent must be a trusted operator-owned staging directory.
        """
        private = tempfile.TemporaryDirectory(prefix='mplug-', dir=parent)
        try:
            folder = Path(private.name)
            os.chmod(folder, 0o700)
            archive_path = folder / 'artifact.mplug'
            with Path(source).open('rb') as incoming, archive_path.open('xb') as outgoing:
                copied = 0
                while chunk := incoming.read(64 * 1024):
                    copied += len(chunk)
                    if copied > self.limits.compressed:
                        raise ArtifactError('Compressed archive size limit')
                    outgoing.write(chunk)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            verified = self.verify(archive_path, expected_digest=expected_digest)
            payload = folder / 'payload'
            payload.mkdir(mode=0o700)
            root = verified.manifest['plugin']['id']
            with zipfile.ZipFile(archive_path) as archive:
                for name, digest in verified.inventory.items():
                    target = payload.joinpath(*portable_path(name).split('/'))
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    actual = hashlib.sha256()
                    with archive.open(root + '/' + name) as incoming, target.open('xb') as outgoing:
                        while chunk := incoming.read(64 * 1024):
                            outgoing.write(chunk)
                            actual.update(chunk)
                    if actual.hexdigest() != digest:
                        raise ArtifactError('Extracted file digest mismatch')
            return private, verified
        except BaseException:
            private.cleanup()
            raise
