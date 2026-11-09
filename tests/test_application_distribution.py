"""Ordinary application CLI, exact archive composition and dependency admission."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import test_application_package as authoring_test
from application_package import assemble_application
from build_distribution import build
from build_inputs import source_input_paths
from modular_platform.artifacts import ArtifactValidator,TrustPolicy,ArtifactError
from modular_platform.catalog import Catalog
from modular_platform.contracts import ContractError
from modular_platform.resolution import resolve_release
from reference_package import toml_value
from test_resolution import ENVIRONMENT


def toml(document):
    return '\n'.join(json.dumps(key)+' = '+toml_value(value) for key,value in document.items())+'\n'


class ApplicationDistribution(unittest.TestCase):
    def setUp(self):
        self.app=authoring_test.ApplicationPackage('test_non_example_repeatable_validated_and_ownership_checked')
        self.app.setUp();self.addCleanup(self.app.doCleanups)
        self.root=self.app.root
        self.policy={'addons':['base','web','mp_example_tasks'],'application_packages':['application.toml']}
        (self.root/'engine/odoo').mkdir(parents=True)
        (self.root/'engine/odoo/__init__.py').write_text('raise RuntimeError("engine import forbidden in source build")',encoding='utf8')
        (self.root/'engine/odoo-bin').write_text('raise RuntimeError("launcher execution forbidden in source build")',encoding='utf8')
        for addon,depends in [('base',[]),('web',['base'])]:
            folder=self.root/'framework_addons'/addon;folder.mkdir(parents=True)
            (folder/'__manifest__.py').write_text(repr(dict(name=addon,version='1.0',depends=depends)),encoding='utf8')
            (folder/'__init__.py').write_text('raise RuntimeError("framework import forbidden in source build")',encoding='utf8')
        for name in ['COPYRIGHT','requirements.txt','.dockerignore']:
            (self.root/name).write_text('fixture\n',encoding='utf8')
        (self.root/'deploy').mkdir()

    def write_policy(self):
        (self.root/'deploy/apps.json').write_text(json.dumps(self.policy,ensure_ascii=False),encoding='utf8')

    def compose(self):
        self.write_policy()
        return build(self.root,self.root/'distribution','deploy/apps.json')

    def extension(self):
        addon='example_tasks_labels'
        directory=self.root/'authoring/apps'/addon;directory.mkdir(parents=True)
        (directory/'__manifest__.py').write_text(repr(dict(name='Labels',version='19.0.0.1.0',depends=['mp_example_tasks'],license='LGPL-3')),encoding='utf8')
        (directory/'__init__.py').write_text('raise RuntimeError("extension import forbidden")',encoding='utf8')
        (directory/'models.py').write_text('from odoo import models, fields\nclass Label(models.Model):\n    _inherit="mp.example.task"\n    custom_label=fields.Char()\n',encoding='utf8')
        manifest=copy.deepcopy(self.app.manifest)
        manifest['plugin'].update(id='dev.example.labels',name='Task labels')
        manifest['runtime']['addon_name']=addon
        manifest['dependencies']['plugins']={'dev.example.tasks':'>=0.1,<0.2'}
        manifest['data']=dict(models=[],extension_targets=['mp.example.task'],contributions=[
            dict(kind='field',id='mp.example.task.custom_label',target='mp.example.task',delete_policy='owned')])
        (self.root/'authoring/labels-plugin.toml').write_text(toml(manifest),encoding='utf8')
        (self.root/'authoring/LICENSE').write_bytes((self.root/'LICENSE').read_bytes())
        (self.root/'authoring/labels.toml').write_text('''schema_version=1
manifest="authoring/labels-plugin.toml"
addon="authoring/apps/example_tasks_labels"
[resources]
"notices/LICENSE"="authoring/LICENSE"
''',encoding='utf8')
        self.policy['addons'].append(addon)
        self.policy['application_packages'].append('authoring/labels.toml')
        return manifest

    def test_cli_produces_repeatable_bytes_and_refuses_overwrite(self):
        command=[sys.executable,'-I',str(ROOT/'tools/package_application.py'),'--source',str(self.root),
                 '--recipe','application.toml','--output',str(self.root/'first.mplug')]
        result=subprocess.run(command,capture_output=True,check=True,text=True)
        receipt=json.loads(result.stdout)
        raw=assemble_application(self.root,'application.toml')[1]
        self.assertEqual((self.root/'first.mplug').read_bytes(),raw)
        self.assertEqual(receipt['digest'],'sha256:'+hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['result'],'assembled_native_application_not_installed_or_trusted')
        again=subprocess.run(command,capture_output=True)
        self.assertNotEqual(again.returncode,0)
        self.assertEqual((self.root/'first.mplug').read_bytes(),raw)

    def test_two_owned_applications_compose_from_exact_archive_bytes(self):
        self.extension()
        inventory=self.compose()
        for recipe in self.policy['application_packages']:
            manifest,raw,files=assemble_application(self.root,recipe)
            descriptor=inventory['artifacts'][manifest['plugin']['id']]
            self.assertEqual((self.root/'distribution/artifacts'/descriptor['file']).read_bytes(),raw)
            prefix='backend/odoo_addons/'+descriptor['addon']+'/'
            for name,data in files.items():
                if name.startswith(prefix):
                    self.assertEqual((self.root/'distribution/addons'/descriptor['addon']/name[len(prefix):]).read_bytes(),data)
        self.assertEqual(inventory['package_composition']['fields']['mp.example.task.custom_label'],'dev.example.labels')

    def test_utf8_operator_policy_preserves_its_profile(self):
        self.policy['profile']='تطبيق مهام مستقل'
        self.assertEqual(self.compose()['policy']['profile'],self.policy['profile'])

    def test_missing_and_incompatible_package_dependencies_refused_before_output(self):
        manifest=self.extension()
        manifest['dependencies']['plugins']={'dev.example.tasks':'>=9'}
        (self.root/'authoring/labels-plugin.toml').write_text(toml(manifest),encoding='utf8')
        with self.assertRaisesRegex(ContractError,'incompatible'):
            self.compose()
        self.assertFalse((self.root/'distribution').exists())

    def test_native_dependency_cannot_hide_missing_package_edge(self):
        manifest=self.extension();manifest['dependencies']['plugins']={}
        (self.root/'authoring/labels-plugin.toml').write_text(toml(manifest),encoding='utf8')
        with self.assertRaisesRegex(ContractError,'lacks a declared package edge'):
            self.compose()
        self.assertFalse((self.root/'distribution').exists())

    def test_dependency_closure_rejects_unadmitted_native_module(self):
        path=self.app.addon/'__manifest__.py';manifest=ast.literal_eval(path.read_text())
        manifest['depends'].append('unadmitted_native_app');path.write_text(repr(manifest),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'unpackaged dependencies'):
            self.compose()
        self.assertFalse((self.root/'distribution').exists())

    def test_external_authoring_inputs_and_resources_are_in_source_identity(self):
        self.extension();self.write_policy()
        inputs=source_input_paths(self.root,'deploy/apps.json')
        for name in ['application.toml','authoring/labels.toml','authoring/labels-plugin.toml',
                     'authoring/LICENSE','authoring/apps/example_tasks_labels/models.py']:
            self.assertIn(name,inputs)
        self.assertNotIn('authoring/apps/example_tasks_labels/__pycache__/anything.pyc',inputs)

    def test_reviewed_catalog_and_whole_release_solver_consume_real_artifacts(self):
        self.extension()
        artifacts=[assemble_application(self.root,path)[1] for path in self.policy['application_packages']]
        digests=frozenset('sha256:'+hashlib.sha256(raw).hexdigest() for raw in artifacts)
        catalog=Catalog(self.root/'catalog',ArtifactValidator(TrustPolicy(approved_digests=digests)))
        for index,raw in enumerate(artifacts):
            incoming=self.root/(str(index)+'.mplug');incoming.write_bytes(raw)
            catalog.add(incoming,expected_digest='sha256:'+hashlib.sha256(raw).hexdigest())
        environment=copy.deepcopy(ENVIRONMENT)
        environment.update(platform_version='0.1.47',core_addons=['base','web'])
        result=resolve_release(catalog.snapshot(),[],environment,{'dev.example.labels':'==0.1.0'})
        self.assertEqual(result['native_order'],['mp_example_tasks','example_tasks_labels'])
        self.assertEqual({item['digest'] for item in result['plugins']},digests)


if __name__=='__main__':unittest.main()
