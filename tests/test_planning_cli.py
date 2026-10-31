"""Actual curated artifacts -> read-only CLI planning -> frozen exact envelope."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.plans import check_bundle,release_lock,data_digest
from modular_platform.resolution import resolve_release
from modular_platform.projection import PLATFORM_VERSION
from reference_package import assemble
from test_plans import base_state, ident, PROVENANCE, STAMP
from test_resolution import ENVIRONMENT


class PlanningCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.config = self.folder / 'operator.json'
        self.input = self.folder / 'proposal.json'
        self.store = self.folder / 'catalog'
        artifacts = []
        digests = []
        for name in ('notes', 'notes_labels', 'canvas'):
            _, raw, _ = assemble(ROOT, 'plugins/' + name + '/plugin.toml')
            path = self.folder / (name + '.mplug')
            path.write_bytes(raw)
            digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
            artifacts.append((path, digest))
            digests.append(digest)
        self.configuration = {'schema_version': 1, 'mode': 'curated', 'approved_digests': digests,
                              'allow_unsigned_development': False, 'generation': 1}
        self.config.write_text(json.dumps(self.configuration))
        catalog = Catalog(self.store, ArtifactValidator(TrustPolicy(approved_digests=frozenset(digests))))
        for path, digest in artifacts:
            catalog.add(path, expected_digest=digest)
        # Current archives require the registered-job API introduced in0.1.8.
        # Model an already compatible empty core, not an implicit core upgrade.
        environment={**copy.deepcopy(ENVIRONMENT),'platform_version':PLATFORM_VERSION}
        provenance={**copy.deepcopy(PROVENANCE),'platform_version':PLATFORM_VERSION}
        state=base_state();state['release_lock']=release_lock(resolve_release([],[],environment,{}),provenance,generation=1,created_at=STAMP)
        state['release_digest']=data_digest(state['release_lock'])
        self.document = {'state': state, 'environment': environment, 'provenance': provenance, 'python_metadata': [],
            'request': {'operation_type': 'install', 'requested': {'org.example.canvas': '>=0.1', 'org.example.notes_labels': '>=0.2'},
                'targets': [{'installation_id': ident(100 + i), 'site_id': ident(20), 'workspace_id': ident(30), 'plugin_id': 'org.example.' + name, 'action': 'install'}
                            for i, name in enumerate(('notes', 'notes_labels', 'canvas'))],
                'operation_id': ident(500), 'created_at': STAMP}}

    def invoke(self, document=None):
        self.input.write_text(json.dumps(document or self.document))
        return subprocess.run([sys.executable, str(ROOT / 'tools/modular.py'), '--config', str(self.config),
            'plugin', 'plan', '--input', str(self.input), '--store', str(self.store)], capture_output=True, text=True)

    def test_actual_curated_plan_is_pure_scoped_reproducible_and_has_one_major_per_alias(self):
        before = {path.relative_to(self.store).as_posix(): path.read_bytes() for path in self.store.rglob('*') if path.is_file()}
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = json.loads(result.stdout)
        self.assertTrue(check_bundle(bundle, self.document['state']))
        self.assertEqual(len(bundle['plan']['artifacts']), 3)
        self.assertEqual(len(bundle['operation_lock']['bindings']), 5)
        self.assertEqual({item['contract_major'] for item in bundle['operation_lock']['bindings']}, {1, 2})
        self.assertTrue(all(item['workspace_id'] == ident(30) for item in bundle['operation_lock']['bindings']))
        self.assertEqual(json.loads(self.invoke().stdout), bundle)
        after = {path.relative_to(self.store).as_posix(): path.read_bytes() for path in self.store.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(bundle['display']['feature_suspension_unloads_code'])
        self.assertIn('Independent local operator approval', bundle['display']['required_local_step'])
        self.assertTrue(bundle['display']['resolution_reasons'])

    def test_development_warning_survives_plan_wrapper_and_read_only_store_denies_mutation(self):
        self.config.write_text(json.dumps({**self.configuration, 'mode': 'development', 'allow_unsigned_development': True}))
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('UNSIGNED DEVELOPMENT ARTIFACT', result.stderr)
        catalog = Catalog(self.store, ArtifactValidator(TrustPolicy(approved_digests=frozenset(self.configuration['approved_digests']))), readonly=True)
        with self.assertRaisesRegex(ValueError, 'Read-only'):
            catalog.quarantine(self.configuration['approved_digests'][0])

    def test_two_workspaces_share_site_installations_with_distinct_scoped_binding_ids(self):
        document = copy.deepcopy(self.document)
        original = list(document['request']['targets'])
        document['request']['targets'].extend({**item, 'workspace_id': ident(31)} for item in original)
        result = self.invoke(document)
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = json.loads(result.stdout)
        self.assertTrue(check_bundle(bundle, document['state']))
        self.assertEqual(len(bundle['operation_lock']['targets']), 6)
        self.assertEqual(len({item['installation_id'] for item in bundle['operation_lock']['targets']}), 3)
        bindings = bundle['operation_lock']['bindings']
        self.assertEqual(len(bindings), 10)
        self.assertEqual(len({item['binding_id'] for item in bindings}), 10)
        self.assertEqual({item['workspace_id'] for item in bindings}, {ident(30), ident(31)})
        bad = copy.deepcopy(document)
        bad['request']['targets'][-1]['installation_id'] = ident(999)
        failed = self.invoke(bad)
        self.assertEqual(failed.returncode, 2)
        self.assertIn('stable plugin installation identity', failed.stderr)

    def test_malformed_or_approval_shaped_input_fails_without_traceback(self):
        for change in ({'approved': True}, {'state': {}}, {'request': {'approved': True}},
                       {'python_metadata': [{'kind': 'source_build', 'command': 'execute'}]}):
            with self.subTest(change=change):
                result = self.invoke({**self.document, **change})
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)['error'], 'VALIDATION_FAILED')
                self.assertNotIn('Traceback', result.stderr)

    def test_current_archives_refuse_legacy_platform_without_catalog_mutation(self):
        before={p.relative_to(self.store).as_posix():p.read_bytes() for p in self.store.rglob('*') if p.is_file()}
        legacy=copy.deepcopy(self.document);legacy['state']=base_state()
        legacy['environment']['platform_version']='0.1.0';legacy['provenance']['platform_version']='0.1.0'
        result=self.invoke(legacy)
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stderr)['error'],'VALIDATION_FAILED')
        self.assertNotIn('Traceback',result.stderr)
        self.assertEqual(before,{p.relative_to(self.store).as_posix():p.read_bytes() for p in self.store.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
