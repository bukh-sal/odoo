"""G5 hostile-byte and immutable-catalog checks; no native runtime is loaded."""
import ast
import copy
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import subprocess
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tools'))
from modular_platform.artifacts import ArchiveLimits, ArtifactError, ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.contracts import ContractError
from reference_package import assemble, toml_value

DEV = TrustPolicy('development', allow_unsigned_development=True)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def inventory(files):
    files = {name: value for name, value in files.items() if name not in ('inventory.json', 'provenance.json')}
    source = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}
    files['provenance.json'] = json.dumps({'schema_version': 1, 'builder': 'hostile-fixture-v1', 'source_files': source}).encode()
    files['inventory.json'] = json.dumps({'schema_version': 1, 'excluded': ['inventory.json'],
        'files': {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}}).encode()
    return files


def pack(files, root='org.example.notes', *, extras=(), compression=zipfile.ZIP_DEFLATED):
    output = io.BytesIO()
    with warnings.catch_warnings(), zipfile.ZipFile(output, 'w') as archive:
        warnings.simplefilter('ignore', UserWarning)
        for name, data in list(files.items()) + list(extras):
            if isinstance(name, zipfile.ZipInfo):
                info = name
            else:
                info = zipfile.ZipInfo(root + '/' + name)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o444) << 16
                info.compress_type = compression
            archive.writestr(info, data)
    return output.getvalue()


def toml(manifest):
    return ('\n'.join(json.dumps(key) + ' = ' + toml_value(value) for key, value in manifest.items()) + '\n').encode()


class Artifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.raw, cls.files = assemble(ROOT, 'plugins/notes/plugin.toml')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = self.folder / 'incoming.mplug'
        self.validator = ArtifactValidator(DEV)

    def verify(self, raw=None, validator=None, **kwargs):
        self.path.write_bytes(self.raw if raw is None else raw)
        return (validator or self.validator).verify(self.path, **kwargs)

    def reject(self, raw, message=None, validator=None):
        with self.assertRaisesRegex(ContractError, message or '.'):
            self.verify(raw, validator)

    def changed_manifest(self, change):
        manifest = copy.deepcopy(self.manifest)
        change(manifest)
        return pack(inventory({**self.files, 'plugin.toml': toml(manifest)}))

    def test_three_actual_reference_archives_and_exact_reproducibility(self):
        for plugin in ('notes', 'notes_labels', 'canvas'):
            with self.subTest(plugin=plugin):
                manifest, raw, files = assemble(ROOT, 'plugins/' + plugin + '/plugin.toml')
                self.assertEqual(raw, assemble(ROOT, 'plugins/' + plugin + '/plugin.toml')[1])
                result = self.verify(raw, expected_digest=digest(raw))
                self.assertEqual(result.digest, digest(raw))
                self.assertEqual(result.expanded_size, sum(map(len, files.values())))
                self.assertFalse(result.trust['signature_verified'])

    def test_never_imports_native_code_and_staging_hashes_written_files(self):
        marker = self.folder / 'PLUGIN_WAS_IMPORTED'
        files = inventory({**self.files, 'backend/odoo_addons/mp_example_notes/__init__.py':
            ('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise RuntimeError("executed")\n').encode()})
        raw = pack(files)
        self.verify(raw)
        self.assertFalse(marker.exists())
        private, result = self.validator.stage(self.path, self.folder, expected_digest=digest(raw))
        with private:
            for name, expected in result.inventory.items():
                self.assertEqual(hashlib.sha256((Path(private.name) / 'payload' / name).read_bytes()).hexdigest(), expected)
            if os.name == 'posix':
                self.assertEqual(stat.S_IMODE(Path(private.name).stat().st_mode), 0o700)
        self.assertFalse(marker.exists())
        self.assertFalse(Path(private.name).exists())

    def test_traversal_absolute_drive_unc_mixed_device_and_control_paths(self):
        names = ('../escape', '/absolute', 'C:/drive', '//server/share', 'org.example.notes/../escape',
                 'org.example.notes\\mixed', 'org.example.notes//empty', 'org.example.notes/./dot',
                 'org.example.notes/CON.txt', 'org.example.notes/trailing.', 'org.example.notes/trailing ',
                 'org.example.notes/control\nname', 'org.example.notes/alternate:stream')
        for name in names:
            with self.subTest(name=repr(name)):
                self.reject(pack(self.files, extras=[(zipfile.ZipInfo(name), b'bad')]))
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), ['incoming.mplug'])

    def test_symlink_fifo_device_and_directory_mode_confusion(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFBLK, stat.S_IFSOCK, stat.S_IFDIR):
            with self.subTest(mode=mode):
                info = zipfile.ZipInfo('org.example.notes/link')
                info.create_system = 3
                info.external_attr = (mode | 0o777) << 16
                self.reject(pack(self.files, extras=[(info, b'/outside')]), 'Links')

    def test_duplicate_case_unicode_and_file_prefix_collisions(self):
        for extras in (
            [('plugin.toml', b'duplicate')], [('PLUGIN.TOML', b'collision')],
            [('notices/caf\u00e9', b'a'), ('notices/cafe\u0301', b'b')],
            [('notices/child', b'a'), ('notices/child/file', b'b')],
            [('notices/Caf\u00e9', b'a'), ('notices/caf\u00e9', b'b')],
        ):
            with self.subTest(extras=[name for name, _ in extras]):
                self.reject(pack(self.files, extras=extras))

    def test_multiple_roots_loose_files_and_root_manifest_disagreement(self):
        self.reject(pack(self.files, root='org.example.other'), 'root')
        self.reject(pack(self.files, extras=[(zipfile.ZipInfo('outside'), b'bad')]))
        self.reject(pack(self.files, extras=[(zipfile.ZipInfo('other/file'), b'bad')]))

    def test_all_six_limits_accept_boundary_and_reject_one_over(self):
        raw = self.raw
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            ratio = max((item.file_size + max(1, item.compress_size) - 1) // max(1, item.compress_size) for item in infos)
        metadata_names = ['plugin.toml', 'inventory.json', 'provenance.json'] + [name for name in self.files if name.startswith('schemas/') or name.endswith('/__manifest__.py')]
        boundaries = {'compressed': len(raw), 'expanded': sum(map(len, self.files.values())),
                      'entries': len(infos), 'per_file': max(map(len, self.files.values())),
                      'ratio': ratio, 'metadata': max(len(self.files[name]) for name in metadata_names)}
        for field, boundary in boundaries.items():
            with self.subTest(limit=field):
                validator = ArtifactValidator(DEV, replace(ArchiveLimits(), **{field: boundary}))
                self.verify(raw, validator)
                self.reject(raw, validator=ArtifactValidator(DEV, replace(ArchiveLimits(), **{field: boundary - 1})))

    def test_zip_bomb_and_forged_directory_entry_counts(self):
        bomb = pack(inventory({**self.files, 'notices/bomb': b'A' * 1024 * 1024}))
        self.reject(bomb, 'ratio')
        for count in (0, 1, 10_001, 65535):
            with self.subTest(count=count):
                forged = bytearray(self.raw)
                struct.pack_into('<HH', forged, len(forged) - 14, count, count)
                self.reject(forged)

    def test_extras_comments_encryption_sfx_trailing_and_header_inconsistency(self):
        info = zipfile.ZipInfo('org.example.notes/notices/link')
        info.extra = b'\x0d\x00\x04\x00link'
        self.reject(pack(self.files, extras=[(info, b'bad')]), 'metadata')
        self.reject(b'#!/bin/sh\n' + self.raw)
        self.reject(self.raw + b'trailing')
        for offset, value in ((6, 1), (18, 999999), (28, 1)):
            with self.subTest(offset=offset):
                raw = bytearray(self.raw)
                struct.pack_into('<H' if offset != 18 else '<L', raw, offset, value)
                self.reject(raw, 'header')
        raw = self.raw.replace(b'org.example.notes/plugin.toml', b'org.example.notes/plu\x00in.toml')
        self.reject(raw)

    def test_outer_digest_inventory_exclusion_extra_file_and_provenance(self):
        with self.assertRaisesRegex(ArtifactError, 'Outer'):
            self.verify(expected_digest='sha256:' + '0' * 64)
        self.reject(pack({**self.files, 'notices/LICENSE': b'changed'}), 'inventory')
        self.reject(pack(self.files, extras=[('notices/unlisted', b'bad')]), 'inventory')
        bad = json.loads(self.files['inventory.json'])
        bad['excluded'].append('plugin.toml')
        self.reject(pack({**self.files, 'inventory.json': json.dumps(bad).encode()}), 'exclusions')
        bad_provenance = b'{"schema_version":1,"builder":"a","source_files":{},"trust_keys":["evil"]}'
        files = {**self.files, 'provenance.json': bad_provenance}
        declared = json.loads(files['inventory.json'])
        declared['files']['provenance.json'] = hashlib.sha256(bad_provenance).hexdigest()
        files['inventory.json'] = json.dumps(declared).encode()
        self.reject(pack(files), 'provenance')

    def test_unknown_sensitive_manifest_keys_and_unsupported_protocols(self):
        changes = [lambda m: m['runtime'].update(install_command='echo bad'),
                   lambda m: m.update(schema_version=2),
                   lambda m: m['compatibility'].update(host_api_major=2),
                   lambda m: m['ui'].update(mode='sandboxed'),
                   lambda m: m['plugin'].update(id='org.example.notes\n')]
        for change in changes:
            with self.subTest(change=change):
                self.reject(self.changed_manifest(change))

    def test_native_manifest_is_static_and_rejects_hooks_activation_version_and_assets(self):
        name = 'backend/odoo_addons/mp_example_notes/__manifest__.py'
        native = ast.literal_eval(self.files[name].decode())
        for extra in ({'pre_init_hook': 'execute'}, {'auto_install': True}, {'version': '19.0.9.0.0'},
                      {'data': ['../outside']}, {'assets': {'web.assets_backend': ['https://evil/script.js']}},
                      {'depends': ['mp_core', 'mp_core']}, {'depends': [{}]}, {'license': 'Proprietary'}):
            with self.subTest(extra=extra):
                self.reject(pack(inventory({**self.files, name: repr({**native, **extra}).encode()})))
        self.reject(pack(inventory({**self.files, name: b'__import__("os").system("whoami")'})))
        self.reject(pack(inventory({**self.files,
            'backend/odoo_addons/mp_example_notes/migrations/0.0.0/pre-evil.py': b'raise RuntimeError()'})), 'migration')

    def test_missing_schema_remote_ref_bad_schema_and_missing_prebuilt_page(self):
        schema_name = self.manifest['services']['provides'][0]['schema']
        for raw in (b'{"$ref":"https://example.invalid/schema"}', b'{"type":"nonsense"}', b'{"type":"string","type":"object"}'):
            with self.subTest(schema=raw):
                self.reject(pack(inventory({**self.files, schema_name: raw})))
        files = dict(self.files)
        del files[schema_name]
        self.reject(pack(inventory(files)), 'schema')
        _, _, canvas = assemble(ROOT, 'plugins/canvas/plugin.toml')
        del canvas['frontend/dist/canvas.js']
        self.reject(pack(inventory(canvas), root='org.example.canvas'), 'asset')

    def test_secret_and_remote_script_lint_redacts_source(self):
        specimens = [('notices/secret', b'-----BEGIN PRIVATE KEY-----\nPRIVATE_VALUE'),
                     ('frontend/dist/app.js', b'import("https://unapproved.invalid/code.js")'),
                     ('frontend/dist/app.html', b'<script src="//unapproved.invalid/a.js"></script>'),
                     ('frontend/dist/app.js', b'const api_key = "PRIVATE_VALUE_123456";'),
                     ('frontend/dist/app.js', b'fetch("https://username:PRIVATE_VALUE@example.invalid/")')]
        for name, data in specimens:
            with self.subTest(name=name):
                with self.assertRaises(ArtifactError) as caught:
                    self.verify(pack(inventory({**self.files, name: data})))
                self.assertNotIn('PRIVATE_VALUE', str(caught.exception))

    def test_external_metadata_accepts_data_and_rejects_every_executable_layout(self):
        manifest = json.loads((ROOT / 'packages/contracts/examples/v1/manifest-external.json').read_text())
        files = {'plugin.toml': toml(manifest), 'notices/LICENSE': b'license'}
        for service in manifest['services']['provides']:
            files[service['schema']] = b'{"type":"object"}'
        raw = pack(inventory(files), root=manifest['plugin']['id'])
        self.assertEqual(self.verify(raw).manifest['runtime']['kind'], 'external_service')
        for name in ('backend/odoo_addons/evil/__init__.py', 'frontend/dist/run.js', 'install.sh',
                     'deploy/compose.yml', 'runtime/image.tar', 'migrations/pre.py', 'schemas/install.py',
                     'notices/installer.sh', 'notices/compose.yml'):
            with self.subTest(name=name):
                self.reject(pack(inventory({**files, name: b'execute'}), root=manifest['plugin']['id']), 'layout|schemas|notices')

    def test_curated_exact_digest_development_opt_in_and_no_self_trust(self):
        self.reject(self.raw, validator=ArtifactValidator(TrustPolicy()))
        self.reject(self.raw, validator=ArtifactValidator(TrustPolicy('development')))
        self.reject(self.raw, validator=ArtifactValidator(TrustPolicy('marketplace', frozenset({digest(self.raw)}))))
        result = self.verify(validator=ArtifactValidator(TrustPolicy(approved_digests=frozenset({digest(self.raw)}), generation=4)))
        self.assertEqual(result.trust['model'], 'operator-approved-exact-digest')
        self.assertEqual(result.trust['policy_generation'], 4)
        self.assertFalse(result.trust['signature_verified'])
        self.assertTrue(self.verify().trust['warnings'])

    def test_catalog_immutable_version_conflicts_trust_change_quarantine_and_corruption(self):
        self.verify()
        catalog = Catalog(self.folder / 'catalog', self.validator)
        first = catalog.add(self.path, expected_digest=digest(self.raw))
        self.assertEqual(first, catalog.add(self.path, expected_digest=digest(self.raw)))
        self.assertEqual(len(catalog.snapshot()), 1)
        changed = pack(inventory({**self.files, 'notices/NEW': b'different bytes'}))
        self.path.write_bytes(changed)
        with self.assertRaisesRegex(ArtifactError, 'Same plugin version'):
            catalog.add(self.path, expected_digest=digest(changed))
        self.assertEqual(catalog.path(first['digest']).read_bytes(), self.raw)
        catalog.validator = ArtifactValidator(TrustPolicy())
        with self.assertRaisesRegex(ArtifactError, 'not approved'):
            catalog.snapshot()
        catalog.validator = self.validator
        blob = catalog.path(first['digest'])
        os.chmod(blob, 0o600)
        blob.write_bytes(b'corrupt')
        self.path.write_bytes(self.raw)
        with self.assertRaisesRegex(ArtifactError, 'corrupt'):
            catalog.add(self.path, expected_digest=digest(self.raw))
        self.assertEqual(blob.read_bytes(), b'corrupt')
        catalog.quarantine(first['digest'])
        self.assertEqual(catalog.snapshot(), [])
        with self.assertRaisesRegex(ArtifactError, 'quarantined'):
            catalog.add(self.path, expected_digest=digest(self.raw))
        self.assertEqual(list(catalog.staging.iterdir()), [])

    def test_real_cli_and_strict_operator_configuration(self):
        config = self.folder / 'operator.json'
        configuration = {'schema_version': 1, 'mode': 'development', 'approved_digests': [],
                         'allow_unsigned_development': True, 'generation': 1}
        config.write_text(json.dumps(configuration))
        self.path.write_bytes(self.raw)
        prefix = [sys.executable, str(ROOT / 'tools/modular.py'), '--config', str(config)]
        completed = subprocess.run(prefix + ['plugin', 'validate', str(self.path), '--digest', digest(self.raw)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('UNSIGNED DEVELOPMENT', completed.stderr)
        self.assertFalse(json.loads(completed.stdout)['trust']['signature_verified'])
        for changed in ({'mode': 'marketplace'}, {'mode': 'curated'}, {'allow_unsigned_development': False},
                        {'generation': True}, {'limits': {'ratio': 0}}, {'trust_from_package': True}):
            with self.subTest(changed=changed):
                config.write_text(json.dumps({**configuration, **changed}))
                completed = subprocess.run(prefix + ['plugin', 'validate', str(self.path), '--digest', digest(self.raw)], capture_output=True, text=True)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(json.loads(completed.stderr)['error'], 'VALIDATION_FAILED')
                self.assertNotIn('Traceback', completed.stderr)


if __name__ == '__main__':
    unittest.main()
