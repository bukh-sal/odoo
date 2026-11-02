"""Dependency maintenance must retain exact independent release authority."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.contracts import ContractError,plan_hash
from modular_platform.operator_os import OperatorError
from modular_platform.plans import check_bundle,data_digest,_display
from modular_platform.release_staging import core_python_changes,validate_core_upgrade,validate_platform_deploy,validate_plugin_core_stability
import test_core_upgrade as core
import test_release_staging as staged
from test_resolution import wheel


def distribution(name,version='1.0',**kwargs):
    value=wheel(name,version,**kwargs);value['kind']='runtime_distribution';value.pop('tags')
    return value


class CorePythonMaintenance(unittest.TestCase):
    pin=core.CoreUpgrade.pin
    prepare=core.CoreUpgrade.prepare

    def setUp(self):
        core.CoreUpgrade.setUp(self)
        for runtime,version,digest in [(self.base,'0.1.20','a'),(self.runtime,'0.1.21','b')]:
            runtime['platform_version']=version
            runtime['inventory']['files']['packages/platform_sdk/modular_platform/projection.py']=digest*64
            runtime['inventory']['files']['addons/mp_core/__manifest__.py']=digest*64
        self.base['native_manifests']['mp_core']['version']='19.0.0.1.20'
        self.runtime['native_manifests']['mp_core']['version']='19.0.0.1.21'
        next(p for p in self.site['native_modules'] if p['addon']=='mp_core')['version']='19.0.0.1.20'
        self.base['python_metadata']=[distribution('Pillow','10.2.0'),distribution('retained','1.0')]
        self.runtime['python_metadata']=[distribution('Pillow','13.0.0'),distribution('retained','1.0')]
        self.runtime['python_lock_digest']='sha256:'+'e'*64
        self.document['state']['release_lock']['python_solution']=[{'name':p['name'].lower(),'version':p['version'],'digest':p['digest']} for p in self.base['python_metadata']]
        self.document['state']['release_digest']=data_digest(self.document['state']['release_lock'])

    def test_complete_solution_dependency_review_hash_and_independent_reconstruction(self):
        bundle=self.prepare();check_bundle(bundle,self.document['state'])
        golden=json.loads((ROOT/'packages/contracts/examples/v1/plan-python-maintenance.json').read_text())
        self.assertEqual(bundle['plan'],golden)
        review=bundle['display']['python_dependency_changes']
        self.assertEqual(review,bundle['operation_lock']['python_dependency_changes'])
        self.assertEqual(review['previous_lock_digest'],self.base['python_lock_digest'])
        self.assertEqual(review['target_lock_digest'],self.runtime['python_lock_digest'])
        self.assertEqual([(p['name'],p['previous']['version'],p['target']['version']) for p in review['distributions']],[('pillow','10.2.0','13.0.0')])
        solved={p['name'].lower():p['version'] for p in bundle['operation_lock']['release']['python_solution']}
        self.assertEqual(solved,{'pillow':'13.0.0','retained':'1.0'})
        validator=staged.StagedPlans.validator(self)
        validator.observer.read=lambda:{'sites':[copy.deepcopy(self.site)],'runtime':copy.deepcopy(self.base)}
        self.assertEqual(validator(bundle),self.document['state'])
        changed=copy.deepcopy(bundle);changed['operation_lock']['python_dependency_changes']['distributions'][0]['previous']['version']='0.0.1'
        changed['plan']['dependency_lock_digest']=data_digest(changed['operation_lock']);changed['plan_hash']=plan_hash(changed['plan'])
        changed['display']=_display(changed['plan'],changed['operation_lock'])
        check_bundle(changed,self.document['state'])
        with self.assertRaisesRegex(OperatorError,'reconstruction'):validator(changed)
        self.runtime['python_metadata'][0]=distribution('Pillow','13.0.1')
        self.assertNotEqual(self.prepare()['plan_hash'],bundle['plan_hash'])

    def test_dependency_review_cannot_be_hidden_even_when_envelope_is_rehashed(self):
        bundle=self.prepare();bundle['display'].pop('python_dependency_changes')
        with self.assertRaisesRegex(ContractError,'Displayed'):check_bundle(bundle,self.document['state'])
        bundle=self.prepare();bundle['operation_lock'].pop('python_dependency_changes')
        bundle['plan']['dependency_lock_digest']=data_digest(bundle['operation_lock']);bundle['plan_hash']=plan_hash(bundle['plan'])
        bundle['display']=_display(bundle['plan'],bundle['operation_lock'])
        validator=staged.StagedPlans.validator(self)
        validator.observer.read=lambda:{'sites':[copy.deepcopy(self.site)],'runtime':copy.deepcopy(self.base)}
        with self.assertRaisesRegex(OperatorError,'reconstruction'):validator(bundle)

    def test_downgrade_removal_duplicate_invalid_metadata_and_environment_are_rejected(self):
        for case in ['downgrade','removal','duplicate','version','digest','kind','interpreter','architecture','markers','missing_markers','same_lock','lock_only','unversioned_platform','missing_sdk_source','missing_core_source']:
            runtime=copy.deepcopy(self.runtime)
            if case=='downgrade':runtime['python_metadata'][0]=distribution('Pillow','9.0')
            elif case=='removal':runtime['python_metadata'].pop()
            elif case=='duplicate':runtime['python_metadata'].append(distribution('PILLOW','13.0.0'))
            elif case=='version':runtime['python_metadata'][0]['version']='invalid'
            elif case=='digest':runtime['python_metadata'][0]['digest']=None
            elif case=='kind':runtime['python_metadata'][0]['kind']='wheel'
            elif case=='interpreter':runtime['python']='3.13.0'
            elif case=='architecture':runtime['architecture']='arm64'
            elif case=='markers':runtime['markers']['sys_platform']='win32'
            elif case=='missing_markers':runtime.pop('markers')
            elif case=='same_lock':runtime['python_lock_digest']=self.base['python_lock_digest']
            elif case=='lock_only':runtime['python_metadata']=copy.deepcopy(self.base['python_metadata'])
            elif case=='unversioned_platform':runtime['platform_version']=self.base['platform_version']
            else:
                name='packages/platform_sdk/modular_platform/projection.py' if case=='missing_sdk_source' else 'addons/mp_core/__manifest__.py'
                runtime['inventory']['files'][name]=self.base['inventory']['files'][name]
            with self.subTest(case=case),self.assertRaises(OperatorError):validate_core_upgrade(self.base,runtime,self.descriptor)

    def test_explicit_pypdf_successor_only_and_same_version_content_change_is_reviewed(self):
        self.base['python_metadata'].append(distribution('PyPDF2','2.12.1'))
        self.runtime['python_metadata'].append(distribution('pypdf','6.21.4'))
        changes=core_python_changes(self.base,self.runtime)['distributions']
        self.assertEqual({p['name'] for p in changes},{'pillow','pypdf','pypdf2'})
        self.runtime['python_metadata'][-1]=distribution('other-pdf','6.21.4')
        with self.assertRaisesRegex(OperatorError,'remove distributions'):core_python_changes(self.base,self.runtime)
        self.runtime['python_metadata']=copy.deepcopy(self.base['python_metadata'])
        self.runtime['python_metadata'][0]['digest']='sha256:'+'f'*64
        change=core_python_changes(self.base,self.runtime)['distributions'][0]
        self.assertEqual(change['previous']['version'],change['target']['version'])
        self.assertNotEqual(change['previous']['digest'],change['target']['digest'])

    def test_normalized_duplicate_cannot_hide_removal_and_base_metadata_is_checked(self):
        self.base['python_metadata'].append(distribution('some_name','1.0'))
        self.base['python_metadata'].append(distribution('Some.Name','2.0'))
        with self.assertRaisesRegex(OperatorError,'duplicate normalized'):core_python_changes(self.base,self.runtime)

    def test_successor_replaces_only_locked_root_and_retained_plugin_requirement_still_denies(self):
        self.base['python_metadata'].append(distribution('PyPDF2','2.12.1'))
        self.runtime['python_metadata'].append(distribution('pypdf','6.21.4'))
        self.document['state']['release_lock']['python_solution'].append(copy.deepcopy(self.base['python_metadata'][-1]))
        self.document['state']['release_digest']=data_digest(self.document['state']['release_lock'])
        unchanged=copy.deepcopy(self.document['state'])
        bundle=self.prepare();check_bundle(bundle,self.document['state'])
        names={p['name'].lower() for p in bundle['operation_lock']['release']['python_solution']}
        self.assertIn('pypdf',names);self.assertNotIn('pypdf2',names)
        self.assertEqual(self.document['state'],unchanged)
        validator=staged.StagedPlans.validator(self)
        validator.observer.read=lambda:{'sites':[copy.deepcopy(self.site)],'runtime':copy.deepcopy(self.base)}
        validator(bundle)
        for item in self.catalog:item['manifest']['runtime']['python_dependencies']=['PyPDF2>=2']
        with self.assertRaisesRegex(ContractError,'Python dependency conflict'):self.prepare()

    def test_complete_target_dependency_constraints_and_plugin_constraints_reject_conflicts(self):
        self.runtime['python_metadata'][0]['requires_dist']=['retained>=2']
        with self.assertRaisesRegex(ContractError,'Python dependency conflict'):self.prepare()
        self.runtime['python_metadata'][0]['requires_dist']=[]
        # Retained curated artifacts constrain the same target solution, even
        # though core maintenance does not upgrade any plugin artifact.
        for item in self.catalog:item['manifest']['runtime']['python_dependencies']=['Pillow<12']
        with self.assertRaisesRegex(ContractError,'Python dependency conflict'):self.prepare()

    def test_static_and_plugin_operations_remain_closed(self):
        with self.assertRaises(OperatorError):validate_platform_deploy(self.base,self.runtime,self.descriptor)
        with self.assertRaises(OperatorError):validate_plugin_core_stability(self.base,self.runtime)


if __name__=='__main__':unittest.main()
