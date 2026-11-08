"""Application-set additions retain core and reject invalid sets before writes."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import test_application_layer as old
import test_application_package as packages
from application_layer import apply_set_layer


class ApplicationSetTests(unittest.TestCase):
    def setUp(self):
        self.base=old.ApplicationLayerTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.root=self.base.root;self.inputs=self.base.inputs
        self.app=self.application('dev.aurora.projects','mp_aurora_projects','mp.aurora.project')
        self.rows=[];self.add_input((self.inputs/'application.mplug').read_bytes());self.add_input(self.app.build()[1])

    def application(self,plugin,addon,model):
        f=packages.ApplicationPackage();f.setUp();self.addCleanup(f.doCleanups)
        f.addon=f.root/'applications'/addon;f.addon.mkdir()
        (f.addon/'__init__.py').write_text('raise RuntimeError("native import forbidden during composition")\n',encoding='utf-8')
        (f.addon/'models.py').write_text('from odoo import models,fields\nclass App(models.Model):\n _name='+repr(model)+'\n name=fields.Char()\n',encoding='utf-8')
        (f.addon/'__manifest__.py').write_text(repr(dict(name='Probe',version='19.0.0.1.0',depends=['web','mp_core'],license='LGPL-3',data=[])),encoding='utf-8')
        f.manifest['plugin'].update(id=plugin,version='0.1.0');f.manifest['runtime']['addon_name']=addon
        f.manifest['data']=dict(models=[model],extension_targets=[],contributions=[dict(kind='model',id=model,target='site',delete_policy='owned')])
        f.write_manifest()
        p=f.root/'application.toml';p.write_text(p.read_text(encoding='utf-8').replace('applications/mp_aurora_tasks','applications/'+addon),encoding='utf-8')
        return f

    def add_input(self,raw):
        name='application-'+str(len(self.rows)+1).zfill(2)+'.mplug';(self.inputs/name).write_bytes(raw)
        self.rows.append(dict(file=name,digest='sha256:'+hashlib.sha256(raw).hexdigest()))

    def replace_input(self,index,raw):
        (self.inputs/self.rows[index]['file']).write_bytes(raw);self.rows[index]['digest']='sha256:'+hashlib.sha256(raw).hexdigest()

    def request(self):
        return dict(schema_version=2,foundation_image_id=self.base.request['foundation_image_id'],
            foundation_inventory_digest=self.base.request['foundation_inventory_digest'],applications=copy.deepcopy(self.rows))

    def refused(self,request=None,pattern=None):
        before=self.base.snapshot()
        guard=self.assertRaisesRegex(ValueError,pattern) if pattern else self.assertRaises(ValueError)
        with guard:apply_set_layer(self.root,self.inputs,request or self.request())
        self.assertEqual(self.base.snapshot(),before)

    def test_multiple_apps_add_slot_and_replace_only_selected_source_without_import(self):
        before=self.base.snapshot();result=apply_set_layer(self.root,self.inputs,self.request())
        self.assertEqual([a['action'] for a in result['applications']],['added','replaced'])
        after=json.loads((self.root/'distribution-inventory.json').read_bytes())
        self.assertEqual(after['policy']['addons'],self.base.inventory['policy']['addons']+['mp_aurora_projects'])
        self.assertEqual(after['policy']['application_packages'],['applications/dev.aurora.projects/application.toml'])
        self.assertEqual((self.root/'addons/mp_core/__manifest__.py').read_bytes(),before['addons/mp_core/__manifest__.py'])
        self.assertEqual(set(after['artifacts']),{'dev.aurora.tasks','dev.aurora.projects'})
        self.assertFalse(result['application_code_executed'])

    def test_exact_unchanged_existing_package_can_accompany_new_app(self):
        old_file=self.root/'artifacts'/self.base.inventory['artifacts']['dev.aurora.tasks']['file']
        self.replace_input(0,old_file.read_bytes());before=self.base.snapshot()
        result=apply_set_layer(self.root,self.inputs,self.request())
        self.assertEqual(next(a for a in result['applications'] if a['plugin_id']=='dev.aurora.tasks')['action'],'unchanged')
        for name,raw in before.items():
            if name.startswith('addons/mp_aurora_tasks/'):self.assertEqual((self.root/name).read_bytes(),raw)

    def test_unknown_fields_schema_type_empty_set_and_duplicate_paths_refuse(self):
        for change in [dict(sql='x'),dict(schema_version=True),dict(applications=[]),dict(applications=[self.rows[0]]*17),
                       dict(applications=[self.rows[0],self.rows[0]])]:
            with self.subTest(change=change):self.refused(dict(self.request(),**change))

    def test_archive_traversal_unknown_row_fields_and_wrong_digest_refuse(self):
        for change in [dict(file='../application-01.mplug'),dict(command='x'),dict(digest='sha256:'+'f'*64)]:
            request=self.request();request['applications'][1].update(change)
            with self.subTest(change=change):self.refused(request)

    def test_new_addon_cannot_shadow_core(self):
        app=self.application('dev.aurora.shadow','web','mp.shadow');self.replace_input(1,app.build()[1]);self.refused(pattern='cannot shadow')

    def test_duplicate_plugin_and_addon_refuse_before_writes(self):
        self.add_input(self.app.build()[1]);self.refused()
        app=self.application('dev.aurora.other','mp_aurora_projects','mp.other');self.replace_input(2,app.build()[1]);self.refused()

    def test_missing_and_incompatible_package_dependencies_refuse(self):
        for dependency in [{'dev.example.missing':'==1.0.0'},{'dev.aurora.tasks':'==9.0.0'}]:
            self.app.manifest['dependencies']['plugins']=dependency;self.app.write_manifest();self.replace_input(1,self.app.build()[1]);self.refused(pattern='Missing or incompatible .*dependency')

    def test_native_missing_dependency_and_undeclared_package_edge_refuse(self):
        p=self.app.addon/'__manifest__.py';native=ast.literal_eval(p.read_text(encoding='utf-8'))
        for dependency in ['missing_native','mp_aurora_tasks']:
            p.write_text(repr(dict(native,depends=native['depends']+[dependency])),encoding='utf-8');self.replace_input(1,self.app.build()[1]);self.refused()

    def test_declared_native_package_edge_is_resolved_from_actual_selected_versions(self):
        p=self.app.addon/'__manifest__.py';native=ast.literal_eval(p.read_text(encoding='utf-8'));native['depends'].append('mp_aurora_tasks')
        p.write_text(repr(native),encoding='utf-8');self.app.manifest['dependencies']['plugins']={'dev.aurora.tasks':'==0.1.1'}
        self.app.write_manifest();self.replace_input(1,self.app.build()[1]);apply_set_layer(self.root,self.inputs,self.request())

    def test_same_version_changed_bytes_and_downgrade_refuse(self):
        for version in ['0.1.0','0.0.9']:
            f=self.base.fixture;f.manifest['plugin']['version']=version;f.write_manifest()
            p=f.addon/'__manifest__.py';native=ast.literal_eval(p.read_text(encoding='utf-8'));native['version']='19.0.'+version
            p.write_text(repr(native),encoding='utf-8');self.replace_input(0,f.build()[1]);self.refused()

    def test_workspace_scope_and_wrong_platform_refuse(self):
        for key,value in [('activation',dict(scopes=['workspace'],supports_feature_suspension=False)),('compatibility',dict(self.app.manifest['compatibility'],platform='>=9,<10'))]:
            original=copy.deepcopy(self.app.manifest);self.app.manifest[key]=value;self.app.write_manifest();self.replace_input(1,self.app.build()[1]);self.refused();self.app.manifest=original

    def test_core_file_and_exact_inventory_byte_drift_refuse(self):
        path=self.root/'distribution-inventory.json';original=path.read_bytes();path.write_text(json.dumps(self.base.inventory,indent=2),encoding='utf-8');self.refused()
        path.write_bytes(original);(self.root/'addons/mp_core/__manifest__.py').write_text("{'version':'19.0.0.1.50'}",encoding='utf-8');self.refused()

    def test_native_cycle_including_framework_refuses(self):
        self.base.inventory['native_addons']['mp_core']['depends']=['mp_aurora_projects']
        path=self.root/'distribution-inventory.json';path.write_text(json.dumps(self.base.inventory),encoding='utf-8')
        self.base.request['foundation_inventory_digest']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest();self.refused(pattern='Cyclic native')

    def test_new_package_cannot_claim_another_app_model(self):
        app=self.application('dev.aurora.conflict','mp_conflict','mp.aurora.task');self.replace_input(1,app.build()[1]);self.refused(pattern='Conflicting (owned data contribution|native model)')

    def test_declared_package_cycle_refuses(self):
        other=self.application('dev.aurora.other','mp_other','mp.other')
        for app,plugin,addon in [(self.app,'dev.aurora.other','mp_other'),(other,'dev.aurora.projects','mp_aurora_projects')]:
            app.manifest['dependencies']['plugins']={plugin:'==0.1.0'};app.write_manifest()
            p=app.addon/'__manifest__.py';native=ast.literal_eval(p.read_text(encoding='utf-8'));native['depends'].append(addon);p.write_text(repr(native),encoding='utf-8')
        self.replace_input(1,self.app.build()[1]);self.add_input(other.build()[1]);self.refused(pattern='[Cc]ycl')

if __name__=='__main__':unittest.main()
