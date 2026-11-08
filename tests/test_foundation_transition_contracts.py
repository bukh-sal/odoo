"""The cleanup recipe adds narrow authority, never a general upgrade bypass."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform import foundation_transition as ft
from modular_platform.contracts import ContractError,validate
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.release_staging import validate_core_upgrade

SITE='00000000-0000-4000-8000-000000000001'


class FoundationTransition(unittest.TestCase):
    def setUp(self):
        names=set(ft.NATIVE_VERSIONS)|{'iap','mp_identity'}
        manifests={n:dict(version=ft.NATIVE_VERSIONS.get(n,('19.0.1.0',None))[0],application=False,auto_install=False) for n in names}
        inventory=dict(files={'addons/mp_core/__manifest__.py':'a'*64},
            policy=dict(profile='foundation',addons=sorted(names),upstream_commit='c'*40),
            native_addons={n:dict(auto_install=False) for n in names},artifacts={})
        self.before=dict(inventory=inventory,inventory_digest=ft.SOURCE_INVENTORY,native_manifests=manifests,
            python='3.12.16',architecture='amd64',markers={},python_metadata=[],python_lock_digest='sha256:'+'e'*64)
        self.after=copy.deepcopy(self.before);self.after['inventory_digest']='sha256:'+'f'*64
        target=self.after['inventory'];target['native_addons'].pop('iap');self.after['native_manifests'].pop('iap')
        for n,(_,v) in ft.NATIVE_VERSIONS.items():self.after['native_manifests'][n]['version']=v
        for n,v in ft.NEW_MODULES.items():
            target['native_addons'][n]=dict(auto_install=False)
            self.after['native_manifests'][n]=dict(version=v,application=True,auto_install=False)
        target['policy']['addons']=sorted(target['native_addons'])
        for name in ('foundation_transition.py','foundation_native.py'):
            target['files']['packages/platform_sdk/modular_platform/'+name]=hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform'/name).read_bytes()).hexdigest()
        for n in ('base','web','base_setup','html_editor','mail','web_tour'):
            manifests[n]['version']=manifests[n]['version'][5:]
            self.after['native_manifests'][n]['version']=self.after['native_manifests'][n]['version'][5:]
        manifests['mp_identity'].pop('version')
        self.after['native_manifests']['mp_identity'].pop('version')
        self.effect=dict(site_id=SITE,mail_installed=True,legacy_local_pipe_count=0,
            iap_tables=[dict(table=n,rows=0,sha256='a'*64) for n in ft.IAP_TABLES],retained_tables=[],
            native_modules=[dict(addon=n,state='installed',version=ft._native_version(manifests[n].get('version','1.0'))) for n in sorted(names)],
            mail_ownership=sorted([dict(name=n,owner=o,model='ir.ui.view',res_id=i+1)
                for o,names in ft.OWNERS.items() for i,n in enumerate(names)],key=lambda r:r['name']))
        self.descriptor=dict(base_image_id=ft.SOURCE_IMAGE,target_image_id='sha256:'+'b'*64)
        self.declaration=dict(schema_version=1,recipe=ft.RECIPE,
            source=dict(image_id=ft.SOURCE_IMAGE,inventory_digest=ft.SOURCE_INVENTORY,
                policy_digest=data_digest(inventory['policy']),core_version='0.1.46'),
            target=dict(image_id=self.descriptor['target_image_id'],inventory_digest=self.after['inventory_digest'],
                policy_digest=data_digest(target['policy']),core_version='0.1.47',
                recipe_sha256=target['files'][ft.RECIPE_PATH],child_sha256=target['files']['packages/platform_sdk/modular_platform/foundation_native.py']),
            source_changes=ft.source_diff(self.before,self.after),site_effects=[self.effect])

    def check(self):
        return ft.validate_transition(self.before,self.after,self.descriptor,self.declaration,site_ids=[SITE],effects=[self.effect])

    def test_exact_owned_transition_and_ordinary_guard_stays_strict(self):
        self.assertTrue(self.check())
        with self.assertRaisesRegex(OperatorError,'policy'):validate_core_upgrade(self.before,self.after,self.descriptor)

    def test_unknown_recipe_and_injected_command_are_rejected_by_contract(self):
        for field,value in [('recipe','arbitrary'),('command','DROP TABLE mail_message')]:
            with self.subTest(field=field):
                d=copy.deepcopy(self.declaration);d[field]=value
                with self.assertRaises(ContractError):validate('foundation-transition',d)

    def test_changed_source_policy_dependency_or_child_is_rejected(self):
        cases=('base','policy','python','child','version','unlisted','auto_install')
        for case in cases:
            with self.subTest(case=case):
                self.setUp()
                if case=='base':self.descriptor['base_image_id']='sha256:'+'0'*64
                if case=='policy':self.after['inventory']['policy']['allow_untrusted']=True
                if case=='python':self.after['python_metadata']=[dict(name='surprise')]
                if case=='child':self.declaration['target']['child_sha256']='0'*64
                if case=='version':self.after['native_manifests']['web']['version']='19.0.999.0'
                if case=='unlisted':self.after['inventory']['files']['addons/mail/unlisted.py']='0'*64
                if case=='auto_install':self.after['native_manifests']['mp_discuss']['auto_install']=True
                with self.assertRaises(OperatorError):self.check()

    def test_unknown_site_ownership_and_stale_data_cannot_reuse_approval(self):
        with self.assertRaises(OperatorError):ft.validate_transition(self.before,self.after,self.descriptor,self.declaration,site_ids=[])
        for case in ('owner','missing','duplicate','local','stale'):
            with self.subTest(case=case):
                self.setUp();d=copy.deepcopy(self.declaration)
                if case=='owner':d['site_effects'][0]['mail_ownership'][0]['owner']='mp_discuss'
                if case=='missing':d['site_effects'][0]['mail_ownership'].pop()
                if case=='duplicate':d['site_effects'][0]['mail_ownership'].append(d['site_effects'][0]['mail_ownership'][0])
                if case=='local':d['site_effects'][0]['legacy_local_pipe_count']=1
                if case=='stale':d['site_effects'][0]['iap_tables'][0]['rows']=1
                with self.assertRaises((OperatorError,ContractError)):
                    ft.validate_transition(self.before,self.after,self.descriptor,d,site_ids=[SITE],effects=[self.effect])

    def test_native_flags_have_exact_installed_and_extracted_module_scope(self):
        changes=ft.native_changes([dict(native_modules=self.effect['native_modules'])],self.declaration)
        bundle=dict(plan=dict(operation_type='core_upgrade',site_ids=[SITE],backup=dict(required=True),destructive=True),
            operation_lock=dict(foundation_transition=self.declaration,native_core_changes=changes,targets=[]))
        self.assertEqual(ft.maintenance_flags(bundle),['-i','mp_discuss,mp_mail_gateway','-u',','.join(r['addon'] for r in changes)])
        bundle['operation_lock']['native_core_changes'].append(dict(addon='account'))
        with self.assertRaises(OperatorError):ft.maintenance_flags(bundle)

    def test_no_mail_source_does_not_silently_install_extracted_apps(self):
        self.effect.update(mail_installed=False,mail_ownership=[])
        self.effect['native_modules']=[m for m in self.effect['native_modules'] if m['addon']!='mail']
        self.assertTrue(self.check())
        changes=ft.native_changes([dict(native_modules=self.effect['native_modules'])],self.declaration)
        bundle=dict(plan=dict(operation_type='core_upgrade',site_ids=[SITE],backup=dict(required=True),destructive=True),
            operation_lock=dict(foundation_transition=self.declaration,native_core_changes=changes,targets=[]))
        self.assertNotIn('-i',ft.maintenance_flags(bundle))


if __name__=='__main__':unittest.main()
