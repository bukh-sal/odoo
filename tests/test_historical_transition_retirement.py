"""Current operator retires closed 46->47/47->49 historical recipes."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]

from modular_platform.approval_validation import IndependentValidator
from modular_platform.native_executor import NativeExecutor, native_maintenance_flags
from modular_platform.operator_os import OperatorError
from modular_platform.plans import check_bundle, data_digest, plan_hash
from modular_platform.release_staging import StageStore


class HistoricalTransitionRetirementTests(unittest.TestCase):
    def test_closed_sdk_modules_and_fixed_recipe_constants_are_absent(self):
        base=ROOT/'packages/platform_sdk/modular_platform'
        for name in ('foundation_transition.py','foundation_native.py','tasks_adoption.py','tasks_adoption_native.py'):
            self.assertFalse((base/name).exists(),name)
        for path in base.glob('*.py'):
            source=path.read_text(encoding='utf8')
            for marker in ('owned-addon-extraction-46-47-v1','owned-native-tasks-adoption-47-49-v1','mp_aurora_tasks'):
                self.assertNotIn(marker,source,str(path))

    def test_forged_foundation_lock_refused_before_check_bundle_work(self):
        bundle={'plan':{},'plan_hash':'fixture','operation_lock':{'foundation_transition':{}},'display':{}}
        with self.assertRaisesRegex(ValueError,'Historical foundation'):
            check_bundle(bundle,{})

    def test_native_executor_refuses_before_plan_or_runtime_access(self):
        executor=NativeExecutor.__new__(NativeExecutor)
        with self.assertRaisesRegex(OperatorError,'Historical foundation'):
            executor._check_operation({'operation_lock':{'foundation_transition':None},'plan':{}})

    def test_independent_validator_refuses_before_catalog_or_observer(self):
        validator=IndependentValidator.__new__(IndependentValidator)
        with self.assertRaisesRegex(OperatorError,'Historical foundation'):
            validator({'operation_lock':{'foundation_transition':{}},'plan':{}})

    def test_cli_foundation_flag_refuses_before_store_catalog_or_stage_creation(self):
        sys.path.insert(0,str(ROOT/'tools'))
        import modular
        with tempfile.TemporaryDirectory(prefix='mp-c01-cli-') as temporary:
            root=Path(temporary);decl=root/'decl.json';decl.write_text('{}')
            trust=root/'trust.json';trust.write_text(json.dumps(dict(schema_version=1,mode='development',approved_digests=[],
                allow_unsigned_development=True,generation=1)))
            args=['--config',str(trust),'plugin','stage-image','--store',str(root/'control'),
                  '--deployment-config',str(root/'target.json'),'--catalog',str(root/'catalog'),
                  '--image-id','sha256:'+'a'*64,'--foundation-transition',str(decl)]
            with patch.object(modular,'configuration',side_effect=AssertionError('trust config accessed')),\
                 patch.object(modular,'Catalog',side_effect=AssertionError('catalog accessed')),\
                 patch('modular_platform.operator_store.OperatorStore',side_effect=AssertionError('store accessed')):
                self.assertEqual(modular.main(args),2)

    def test_fully_rehashed_historical_bundle_never_reaches_validation_or_apply(self):
        import test_release_staging as fixtures
        case=fixtures.StagedPlans()
        case.setUp()
        original=case.prepare()
        self.assertTrue(check_bundle(original,case.document['state']))
        self.assertEqual(case.validator()(original),case.document['state'])
        for declaration in (None, {}, {'recipe':'retired'}):
            with self.subTest(declaration=declaration):
                bundle=copy.deepcopy(original)
                bundle['operation_lock']['foundation_transition']=declaration
                bundle['plan']['dependency_lock_digest']=data_digest(bundle['operation_lock'])
                bundle['plan_hash']=plan_hash(bundle['plan'])
                self.assertEqual(bundle['plan']['dependency_lock_digest'],data_digest(bundle['operation_lock']))
                self.assertEqual(bundle['plan_hash'],plan_hash(bundle['plan']))
                with self.assertRaisesRegex(ValueError,'Historical foundation'):
                    check_bundle(bundle,case.document['state'])
                validator=IndependentValidator.__new__(IndependentValidator)
                validator.catalog=Mock();validator.observer=Mock()
                with self.assertRaisesRegex(OperatorError,'Historical foundation'):
                    validator(bundle)
                validator.catalog.snapshot.assert_not_called()
                validator.observer.read.assert_not_called()
                executor=NativeExecutor.__new__(NativeExecutor)
                executor.store=Mock();executor.store.bundle.return_value=bundle
                with self.assertRaisesRegex(OperatorError,'Historical foundation'):
                    executor.apply(bundle['plan']['operation_id'])
                executor.store.reserve.assert_not_called()
                with self.assertRaisesRegex(OperatorError,'Historical foundation'):
                    native_maintenance_flags(bundle,{})

    def test_old_staged_record_refuses_before_image_or_runtime_io(self):
        with tempfile.TemporaryDirectory(prefix='mp-c01-stage-') as temporary:
            root=Path(temporary);store=Mock();store.root=root
            stage=StageStore.__new__(StageStore);stage.store=store;stage.configuration={};stage.root=root/'releases'
            stage.root.mkdir();descriptor={'stage_digest':'sha256:'+'a'*64,'base_image_id':'sha256:'+'b'*64,
                'target_image_id':'sha256:'+'c'*64,'inventory_digest':'sha256:'+'d'*64,'runtime_digest':'sha256:'+'e'*64}
            (stage.root/'active.json').write_text(json.dumps(descriptor))
            (stage.root/(descriptor['stage_digest'][7:]+'.json')).write_text(json.dumps(
                {'foundation_transition':{},'base_configuration':{},'image_id':descriptor['target_image_id'],
                 'runtime':{'inventory_digest':'sha256:'+'f'*64}}))
            with patch('modular_platform.release_staging.verify_private_directory'),\
                 patch('modular_platform.release_staging.inspect_image',side_effect=AssertionError('image inspected')),\
                 patch('modular_platform.release_staging.runtime_inputs',side_effect=AssertionError('runtime observed')):
                with self.assertRaisesRegex(OperatorError,'Historical foundation'):
                    stage.load(descriptor,recheck=False)


if __name__=='__main__':
    unittest.main()
