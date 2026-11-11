"""Content-addressed OCI layer proofs, including hidden lower-layer app leaks."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from clean_image_audit import audit_image


def layer(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name, value in entries.items():
            entry = tarfile.TarInfo(name)
            if isinstance(value, tuple):
                entry.type = tarfile.SYMTYPE
                entry.linkname = value[0]
                archive.addfile(entry)
            else:
                entry.size = len(value)
                archive.addfile(entry, io.BytesIO(value))
    return stream.getvalue()


def export(path, layers, *, tamper=False):
    blobs = {}

    def blob(raw):
        digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
        blobs['blobs/sha256/' + digest[7:]] = raw
        return dict(digest=digest, size=len(raw))

    descriptors = [blob(gzip.compress(raw, mtime=0)) for raw in layers]
    diffs = ['sha256:' + hashlib.sha256(raw).hexdigest() for raw in layers]
    config = dict(architecture='amd64', os='linux', rootfs=dict(type='layers', diff_ids=diffs),
        config=dict(User='10001:10001', WorkingDir='/opt/modular',
            Entrypoint=['/venv/bin/python', '/opt/modular/tools/start_worker.py'],
            Cmd=['-c', '/run/secrets/odoo_config'], Env=['LANG=C.UTF-8']))
    cfg = blob(json.dumps(config).encode())
    manifest = blob(json.dumps(dict(schemaVersion=2, config=cfg, layers=descriptors)).encode())
    blobs['index.json'] = json.dumps(dict(schemaVersion=2, manifests=[manifest])).encode()
    if tamper:
        name = 'blobs/sha256/' + descriptors[0]['digest'][7:]
        blobs[name] += b'changed'
    with tarfile.open(path, 'w') as archive:
        for name, raw in blobs.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            archive.addfile(entry, io.BytesIO(raw))
    inspection = dict(Id=cfg['digest'], Architecture='amd64', RootFS=dict(Layers=diffs), Config=config['config'])
    return cfg['digest'], inspection


class CleanImageAudit(unittest.TestCase):
    def check(self, extra=None, *, tamper=False, source_ancestor=False, changed_expected=False):
        expected = {'tools/start_worker.py': hashlib.sha256(b'guarded bootstrap').hexdigest()}
        entries = {'opt/modular/tools/start_worker.py': b'guarded bootstrap',
            'usr/local/bin/rtlcss': ('../../../opt/stock-rtl/node_modules/rtlcss/bin/rtlcss.js',)}
        if changed_expected:
            expected['tools/start_worker.py'] = '0' * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'image.tar'
            raws = [layer(extra)] if extra else []
            raws.append(layer(entries))
            image, inspection = export(path, raws, tamper=tamper)
            before = copy.deepcopy(inspection)
            result = audit_image(path, image, inspection, expected,
                source_layers=inspection['RootFS']['Layers'] if source_ancestor else ['sha256:' + 'f' * 64])
            self.assertEqual(inspection, before)
            return result

    def test_content_and_layer_bindings_accept_exact_payload_and_stock_rtl_link(self):
        result = self.check({'etc/apt/sources.list.d/.wh.debian.sources': b''})
        self.assertEqual(result['project_files'], 1)
        self.assertEqual(len(result['layers']), 2)
        self.assertTrue(result['source_image_not_final_ancestor'])

    def test_hidden_lower_app_file_cannot_be_masked_by_final_clean_payload(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected project file'):
            self.check({'opt/modular/addons/removed_app/business.py': b'app bytes'})

    def test_project_whiteout_is_rejected_even_without_visible_app_file(self):
        for path in ('opt/modular/addons/.wh.removed_app', 'opt/.wh.modular',
                'opt/.wh..wh..opq', '.wh.opt'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'whiteout'):
                self.check({path: b''})

    def test_source_checkout_and_linked_source_are_rejected(self):
        for entries in ({'source/tools/host_operator.py': b'host-only'},
                {'usr/local/bin/hidden': ('/opt/modular/addons/removed_app/business.py',)}):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.check(entries)

    def test_unsafe_paths_changed_blob_and_source_ancestry_are_rejected(self):
        for options in (dict(extra={'opt/modular/../escape': b'bad'}),
                dict(tamper=True), dict(source_ancestor=True), dict(changed_expected=True)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.check(**options)


if __name__ == '__main__':
    unittest.main()
