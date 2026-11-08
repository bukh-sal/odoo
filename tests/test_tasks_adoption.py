"""Synthetic closed-recipe image/data guard cases; no runtime upgrade claim."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform import tasks_adoption as ta
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.release_staging import validate_core_upgrade
from modular_platform.contracts import ContractError


class TasksAdoption(unittest.TestCase):
    def setUp(self):
        names=['base','web','mp_core','mp_aurora_tasks','maintenance']
        manifests={n:dict(version='19.0.1.0',auto_install=False,depends=[]) for n in names}
        manifests['mp_core']['version']='19.0.0.1.47'
        manifests['mp_aurora_tasks'].update(version='19.0.0.1.0',depends=['web'])
        refs={f'org.example.ref{i}':dict(digest='sha256:'+str(i)*64) for i in range(1,6)}
        files={'addons/mp_core/__manifest__.py':'a'*64,'addons/mp_aurora_tasks/__manifest__.py':'b'*64}
        self.before=dict(platform_version='0.1.47',inventory_digest=ta.SOURCE_INVENTORY,
            python='3.12.16',architecture='amd64',markers={},python_metadata=[],python_lock_digest='sha256:'+'e'*64,
            native_manifests=manifests,inventory=dict(files=files,native_addons={n:{} for n in names},artifacts=refs,
                                                    policy=dict(addons=names,profile='owned')))
        self.after=copy.deepcopy(self.before)
        self.after.update(platform_version='0.1.49',inventory_digest='sha256:'+'f'*64)
        self.after['native_manifests']['mp_core']['version']='19.0.0.1.49'
        self.after['native_manifests']['mp_aurora_tasks'].update(version='19.0.0.2.2',depends=['web','mp_core'])
        self.after['inventory']['policy']['application_packages']=['plugins/aurora_tasks/application.toml']
        self.after['inventory']['artifacts'][ta.APP]=dict(addon=ta.ADDON,digest=ta.ARTIFACT,file=ta.APP+'-0.2.2.mplug',plugin_id=ta.APP,version=ta.VERSION)
        for path in [ta.RECIPE_PATH,ta.CHILD_PATH]:
            self.after['inventory']['files'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        self.after['inventory']['files']['addons/mp_core/__manifest__.py']='c'*64
        self.after['inventory']['files']['addons/mp_aurora_tasks/__manifest__.py']='d'*64
        self.after['inventory']['files']['artifacts/'+ta.APP+'-0.2.2.mplug']=ta.ARTIFACT[7:]
        self.declaration=json.loads((ROOT/'packages/contracts/examples/v1/foundation-transition/tasks-adoption.json').read_bytes())
        d=self.declaration
        d['source']['policy_digest']=data_digest(self.before['inventory']['policy'])
        d['target'].update(inventory_digest=self.after['inventory_digest'],policy_digest=data_digest(self.after['inventory']['policy']),
            recipe_sha256=self.after['inventory']['files'][ta.RECIPE_PATH],child_sha256=self.after['inventory']['files'][ta.CHILD_PATH])
        d['source_changes']=ta.source_diff(self.before,self.after)
        d['site_effects'][0]['native_modules'].sort(key=lambda r:r['addon'])
        self.descriptor=dict(base_image_id=ta.SOURCE_IMAGE,target_image_id=d['target']['image_id'])
        self.site=d['site_effects'][0]['site_id']

    def check(self):
        return ta.validate_transition(self.before,self.after,self.descriptor,self.declaration,site_ids=[self.site])

    def test_closed_source_target_and_ordinary_core_guard(self):
        self.assertTrue(self.check())
        with self.assertRaises(OperatorError):validate_core_upgrade(self.before,self.after,self.descriptor)
        effect=self.declaration['site_effects'][0]
        changes=ta.native_changes([dict(site_id=self.site,native_modules=effect['native_modules'])],self.declaration)
        self.assertEqual([r['addon'] for r in changes],['mp_core','mp_aurora_tasks'])
        self.assertEqual(ta.adoption_target(self.declaration)['workspace_id'],None)

    def test_source_dependency_archive_policy_or_source_drift_denied(self):
        for case in ['source','python','archive','policy','unlisted','child','other_manifest','added_module']:
            with self.subTest(case=case):
                self.setUp()
                if case=='source':self.descriptor['base_image_id']='sha256:'+'0'*64
                if case=='python':self.after['python_lock_digest']='sha256:'+'0'*64
                if case=='archive':self.after['inventory']['artifacts']['org.example.ref1']['digest']='sha256:'+'0'*64
                if case=='policy':self.after['inventory']['policy']['unreviewed']=True
                if case=='unlisted':self.after['inventory']['files']['addons/web/extra.py']='0'*64
                if case=='child':self.declaration['target']['child_sha256']='0'*64
                if case=='other_manifest':self.after['native_manifests']['web']['version']='19.0.999.0'
                if case=='added_module':self.after['inventory']['native_addons']['surprise']={}
                with self.assertRaises((OperatorError,ContractError)):self.check()

    def test_incomplete_duplicate_or_stale_application_witnesses_denied(self):
        effect=self.declaration['site_effects'][0]
        for change in ['missing','duplicate','absent','stage_duplicate']:
            with self.subTest(change=change):
                self.setUp();effect=self.declaration['site_effects'][0]
                if change=='missing':effect['retained_tables'].pop()
                if change=='duplicate':effect['retained_tables'].append(effect['retained_tables'][0])
                if change=='absent':effect['tasks_installed']=False
                if change=='stage_duplicate':effect['stage_additions']=[dict(list_id=1,done=False)]*2
                with self.assertRaises((OperatorError,ContractError)):self.check()
        self.setUp();stale=copy.deepcopy(self.declaration['site_effects']);stale[0]['retained_tables'][0]['rows']=1
        with self.assertRaises(OperatorError):
            ta.validate_transition(self.before,self.after,self.descriptor,self.declaration,site_ids=[self.site],effects=stale)

    def test_absent_native_tasks_stays_absent_with_same_available_archive(self):
        effect=self.declaration['site_effects'][0]
        effect.update(tasks_installed=False,native_modules=[dict(addon='mp_core',state='installed',version='19.0.0.1.47')],retained_tables=[],stage_additions=[])
        self.assertTrue(self.check())
        self.assertIsNone(ta.adoption_target(self.declaration))
        self.assertEqual(len(ta.native_changes([dict(site_id=self.site,native_modules=effect['native_modules'])],self.declaration)),1)


if __name__=='__main__':unittest.main()
