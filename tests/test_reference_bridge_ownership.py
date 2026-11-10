"""Reference archive ownership and generic worker operator source guards.

No app source is read by the generic worker operator; native installation/archive
integrity is enforced by the image inventory, worker_start and catalog layers.
"""
import ast
import hashlib
import io
import json
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
from modular_platform.worker_operator import WorkerOperator
from reference_package import assemble

CORE='framework_addons/mp_core'
APP='examples/mp_example_notes_stats'
BRIDGE=('external_job.py','external_authority.py')
GENERIC=('job_runner.py','worker_start.py','worker_authority.py','worker_dispatch.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_runtime(*,connector_metadata=False,app_files=True,artifact_only=False,bridge_hashes=None):
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
        for index,name in enumerate(BRIDGE):
            value=(bridge_hashes or {}).get(name,'0'*64)
            files['addons/mp_example_notes_stats/'+name]=value
    return {'inventory_digest':'sha256:'+'a'*64,
            'inventory':{'files':files,'native_addons':native_addons,'artifacts':artifacts}}


def operator():
    value=WorkerOperator.__new__(WorkerOperator)
    value.target={'project':'fixture-project','deployment_id':'fixture-deployment','image_id':'sha256:'+'b'*64,
                  'sites':[{'database':'fixture-db'}]}
    value.config={'authority_volume':'fixture-authority'}
    return value


class ReferenceBridgeOwnership(unittest.TestCase):
    def test_generic_and_external_only_jobs_do_not_admit_app_source(self):
        baseline=operator()._job_arguments(current_runtime(connector_metadata=False,app_files=False),'fixture-operation')
        self.assertIn('modular_platform.job_runner',baseline)
        external=operator()._job_arguments(current_runtime(connector_metadata=False,app_files=False,artifact_only=True),'fixture-operation')
        self.assertEqual(external,baseline)

    def test_inventoried_reference_app_not_checkout_bound(self):
        # Inventory bytes deliberately differ from the checkout. The generic
        # operator must not read examples/addons app source or add a guard.
        runtime=current_runtime(connector_metadata=True,app_files=True,
                                bridge_hashes={name:'f'*64 for name in BRIDGE})
        baseline=operator()._job_arguments(current_runtime(connector_metadata=False,app_files=False),'fixture-operation')
        original=Path.read_bytes; read=[]
        def spy(path):
            read.append(path.as_posix())
            return original(path)
        with patch.object(Path,'read_bytes',spy):
            actual=operator()._job_arguments(runtime,'fixture-operation')
        self.assertEqual(actual,baseline)
        self.assertFalse(any('mp_example_notes_stats' in path for path in read),read)
        self.assertFalse(any(path.endswith(name) for path in read for name in BRIDGE),read)

    def test_generic_runner_and_job_dispatch_mismatches_refuse(self):
        for relative in [*(f'packages/platform_sdk/modular_platform/{name}' for name in GENERIC),
                         'addons/mp_core/job_dispatch.py']:
            runtime=current_runtime(connector_metadata=False,app_files=False)
            runtime['inventory']['files'][relative]='0'*64
            with self.subTest(relative=relative),self.assertRaises(OperatorError):
                operator()._job_arguments(runtime,'fixture-operation')

    def test_worker_operator_has_no_fixed_connector_source_coupling(self):
        source=(ROOT/'packages/platform_sdk/modular_platform/worker_operator.py').read_text(encoding='utf8')
        tree=ast.parse(source)
        names={node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
        strings={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
        forbidden=('CONNECTOR_ADDON','CONNECTOR_PLUGIN','CONNECTOR_BRIDGE','reviewed_connector_source')
        self.assertFalse(names & set(forbidden))
        for value in ('mp_example_notes_stats','org.example.notes_stats','external_job.py','external_authority.py'):
            self.assertNotIn(value,strings)
            self.assertNotIn(value,source)
        self.assertNotIn('examples/',source)
        self.assertNotIn('addons/mp_example_notes_stats',source)

    def test_new_reference_archive_is_validated_and_contains_moved_bridge(self):
        plugin=tomllib.loads((ROOT/'plugins/notes_stats/plugin.toml').read_text(encoding='utf8'))['plugin']
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
