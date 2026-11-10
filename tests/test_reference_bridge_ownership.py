"""Reference bridge ownership, worker selection guard and reference archive identity."""
import hashlib
import io
import json
import ast
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'tests')]
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.operator_os import OperatorError
from modular_platform.worker_operator import WorkerOperator,reviewed_connector_source
from reference_package import assemble

CORE='framework_addons/mp_core'
APP='examples/mp_example_notes_stats'
BRIDGE=('external_job.py','external_authority.py')
GENERIC=('job_runner.py','worker_start.py','worker_authority.py','worker_dispatch.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_runtime(*,connector_metadata=False,app_files=True,artifact_only=False):
    files={}
    for name in GENERIC:
        files['packages/platform_sdk/modular_platform/'+name]=digest(ROOT/'packages/platform_sdk/modular_platform'/name)
    files['addons/mp_core/job_dispatch.py']=digest(ROOT/CORE/'job_dispatch.py')
    native_addons={'mp_core':{},'mp_shell':{}}
    artifacts={}
    if connector_metadata:
        native_addons['mp_example_notes_stats']={}
    if artifact_only:
        artifacts['org.example.document_stats']={'runtime':'external_service'}
    if app_files:
        for name in BRIDGE:
            files['addons/mp_example_notes_stats/'+name]=digest(ROOT/APP/name)
    return {'inventory_digest':'sha256:'+'a'*64,
            'inventory':{'files':files,'native_addons':native_addons,'artifacts':artifacts}}


def operator():
    value=WorkerOperator.__new__(WorkerOperator)
    value.target={'project':'fixture-project','deployment_id':'fixture-deployment','image_id':'sha256:'+'b'*64,
                  'sites':[{'database':'fixture-db'}]}
    value.config={'authority_volume':'fixture-authority'}
    return value


class ReferenceBridgeOwnership(unittest.TestCase):
    def test_worker_guard_generic_job_does_not_read_optional_app(self):
        with patch('modular_platform.worker_operator.reviewed_connector_source',side_effect=AssertionError('generic job read connector source')):
            arguments=operator()._job_arguments(current_runtime(connector_metadata=False,app_files=False),'fixture-operation')
        self.assertIn('modular_platform.job_runner',arguments)

    def test_external_service_without_connector_does_not_require_app(self):
        with patch('modular_platform.worker_operator.reviewed_connector_source',side_effect=AssertionError('external-only job read connector source')):
            operator()._job_arguments(current_runtime(connector_metadata=False,app_files=False,artifact_only=True),'fixture-operation')

    def test_connector_coherent_passes(self):
        arguments=operator()._job_arguments(current_runtime(connector_metadata=True,app_files=True),'fixture-operation')
        self.assertIn('modular_platform.job_runner',arguments)

    def test_missing_or_changed_each_bridge_refuses(self):
        for name in BRIDGE:
            runtime=current_runtime(connector_metadata=True,app_files=True)
            runtime['inventory']['files'].pop('addons/mp_example_notes_stats/'+name)
            with self.subTest(case='missing',name=name),self.assertRaises(OperatorError):
                operator()._job_arguments(runtime,'fixture-operation')
            runtime=current_runtime(connector_metadata=True,app_files=True)
            runtime['inventory']['files']['addons/mp_example_notes_stats/'+name]='0'*64
            with self.subTest(case='changed',name=name),self.assertRaises(OperatorError):
                operator()._job_arguments(runtime,'fixture-operation')

    def test_inconsistent_connector_metadata_cannot_skip_guard(self):
        runtime=current_runtime(connector_metadata=False,app_files=True)
        with self.assertRaisesRegex(OperatorError,'Connector inventory'):
            operator()._job_arguments(runtime,'fixture-operation')
        runtime=current_runtime(connector_metadata=True,app_files=False)
        with self.assertRaises(OperatorError):
            operator()._job_arguments(runtime,'fixture-operation')

    def test_generic_runner_and_job_dispatch_mismatches_refuse(self):
        for relative in [*(f'packages/platform_sdk/modular_platform/{name}' for name in GENERIC),
                         'addons/mp_core/job_dispatch.py']:
            runtime=current_runtime(connector_metadata=False,app_files=False)
            runtime['inventory']['files'][relative]='0'*64
            with self.subTest(relative=relative),self.assertRaises(OperatorError):
                operator()._job_arguments(runtime,'fixture-operation')

    def test_connector_source_resolution_supports_both_owned_layouts(self):
        with tempfile.TemporaryDirectory(prefix='mp-connector-layout-') as temporary:
            root=Path(temporary)
            for relative in ('examples/mp_example_notes_stats','addons/mp_example_notes_stats'):
                target=root/relative
                target.mkdir(parents=True)
                for name in BRIDGE:
                    (target/name).write_text(name,encoding='utf8')
            self.assertEqual(reviewed_connector_source(root),root/'examples/mp_example_notes_stats')
            import shutil
            shutil.rmtree(root/'examples/mp_example_notes_stats')
            self.assertEqual(reviewed_connector_source(root),root/'addons/mp_example_notes_stats')

    def test_new_reference_archive_is_validated_and_contains_moved_bridge(self):
        plugin= tomllib.loads((ROOT/'plugins/notes_stats/plugin.toml').read_text(encoding='utf8'))['plugin']
        native=ast.literal_eval((ROOT/APP/'__manifest__.py').read_text(encoding='utf8'))
        _,raw,_=assemble(ROOT,'plugins/notes_stats/plugin.toml')
        with tempfile.TemporaryDirectory(prefix='mp-notes-stats-archive-') as temporary:
            path=Path(temporary)/('org.example.notes_stats-'+plugin['version']+'.mplug')
            path.write_bytes(raw)
            verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(path)
        self.assertEqual(verified.manifest['plugin']['version'],plugin['version'])
        self.assertEqual(verified.manifest['runtime']['addon_name'],'mp_example_notes_stats')
        self.assertRegex(verified.digest,r'^sha256:[0-9a-f]{64}$')
        prefix='org.example.notes_stats/backend/odoo_addons/mp_example_notes_stats/'
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=set(archive.namelist())
            for name in BRIDGE:
                self.assertIn(prefix+name,names)
            job=archive.read(prefix+'external_job.py')
            authority=archive.read(prefix+'external_authority.py')
            self.assertIn(b'from .external_authority import authorize_analysis',job)
            self.assertIn(b'from odoo.addons.mp_core import job_dispatch as jobs',job)
            self.assertIn(b'from odoo.addons.mp_core.dispatch import CallFrame',authority)
            self.assertIn(("version':'"+native['version']+"'").encode(),archive.read(prefix+'__manifest__.py'))


if __name__=='__main__':
    unittest.main()
