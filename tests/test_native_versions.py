"""Real pinned parser, wide numeric boundaries and exact core-patch admission."""
import copy
import hashlib
from pathlib import Path
import random
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.contracts import native_version,package_version,ContractError
from modular_platform.native_versions import PARSER_PATH,SOURCE_SHA256,TARGET_SHA256,corrected_parser,patch_record
from modular_platform.release_staging import validate_core_upgrade,validate_platform_deploy,validate_plugin_core_stability
from modular_platform.operator_os import OperatorError
import test_core_upgrade as core

def parser(raw,*,selftest=False):
    namespace={'__name__':'__main__' if selftest else 'qualified_native_parser'}
    exec(compile(raw,'pinned-native-parser','exec'),namespace)
    return namespace['parse_version']

class NativeVersions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(ROOT/PARSER_PATH).read_bytes();cls.corrected=corrected_parser(cls.raw)
        cls.original=staticmethod(parser(cls.raw));cls.native=staticmethod(parser(cls.corrected))

    def test_original_counterexample_is_fixed_without_restricting_package_spelling(self):
        old,new='0.99999999.0','0.100000000.0'
        self.assertLess(package_version(old),package_version(new))
        self.assertGreater(self.original(native_version(old)),self.original(native_version(new)))
        self.assertLess(self.native(native_version(old)),self.native(native_version(new)))
        values=['0.1.0','0.1.9','0.1.10','0.2.0','0.3.0',old,new,'1.0.0','99999999.0.0','100000000.0.0']
        self.assertEqual(sorted(values,key=package_version),sorted(values,key=lambda v:self.native(native_version(v))))

    def test_width_prefix_handles_very_wide_components_without_integer_conversion(self):
        for size in [8,9,10,99,100,999,1000,4000]:
            old='0.'+'9'*(size-1)+'.0';new='0.1'+'0'*(size-1)+'.0'
            self.assertLess(package_version(old),package_version(new))
            self.assertLess(self.native(native_version(old)),self.native(native_version(new)))

    def test_upstream_self_vectors_and_legacy_order_and_equality_are_preserved(self):
        parser(self.raw,selftest=True);parser(self.corrected,selftest=True)
        rng=random.Random(21)
        values=['0','0.0','0.0.0','1.0','1.0.0','2.4a1','2.4b1','2.4rc1','2.4','2.4-1','2.4.1',
            '9.0.2.0','10.0.2.0','saas~18.1.1.0','19.0.0.1.0','19.0.0.1.1']
        for _ in range(150):
            value='.'.join(str(rng.randrange(100000000)) for n in range(rng.randrange(1,6)))
            values.extend([value,value+'dev1',value+'rc2'])
        for first in values:
            old_first,new_first=self.original(first),self.native(first)
            self.assertTrue(all(isinstance(token,str) for token in new_first))
            for second in values:
                old_second,new_second=self.original(second),self.native(second)
                self.assertEqual((old_first>old_second)-(old_first<old_second),(new_first>new_second)-(new_first<new_second))

    def test_exact_input_output_and_notices_are_bound(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),SOURCE_SHA256)
        self.assertEqual(hashlib.sha256(self.corrected).hexdigest(),TARGET_SHA256)
        self.assertEqual(self.corrected.splitlines()[0],self.raw.splitlines()[0])
        with self.assertRaises(ValueError):corrected_parser(self.raw+b'\n')
        self.assertEqual((ROOT/PARSER_PATH).read_bytes(),self.raw)

    def test_invalid_author_spellings_remain_rejected(self):
        for value in ['v1.0.0','1.0','01.0.0','1.0.0rc1','1.0.0.post1','1!1.0.0','1.0.0+build','1.0.0\n']:
            with self.assertRaises(ContractError):native_version(value)

class NativePatchAdmission(unittest.TestCase):
    def setUp(self):
        f=core.CoreUpgrade();f.setUp();self.base=copy.deepcopy(f.base);self.runtime=copy.deepcopy(f.base);self.descriptor=f.descriptor
        for runtime in [self.base,self.runtime]:
            runtime['inventory']['native_addons']['mp_compat']={'depends':['web']}
            runtime['native_manifests']['mp_compat']={'version':'19.0.0.1.0'}
            runtime['inventory']['files']['addons/mp_compat/__manifest__.py']='1'*64
            runtime['inventory']['files'][PARSER_PATH]=SOURCE_SHA256
        self.runtime['native_manifests']['mp_compat']['version']='19.0.0.1.1'
        self.runtime['inventory']['files']['addons/mp_compat/__manifest__.py']='2'*64
        self.runtime['inventory']['files'][PARSER_PATH]=TARGET_SHA256
        self.runtime['inventory']['generated_patches']=self.base['inventory']['generated_patches']+[patch_record()]

    def test_only_exact_core_patch_with_versioned_compatibility_addon_is_allowed(self):
        diff,changes=validate_core_upgrade(self.base,self.runtime,self.descriptor)
        self.assertEqual(changes,[{'addon':'mp_compat','previous_version':'19.0.0.1.0','target_version':'19.0.0.1.1','migrations':[]}])
        self.assertIn(PARSER_PATH,[entry['path'] for entry in diff])
        with self.assertRaises(OperatorError):validate_platform_deploy(self.base,self.runtime,self.descriptor)
        with self.assertRaises(OperatorError):validate_plugin_core_stability(self.base,self.runtime)

    def test_forged_unknown_unversioned_and_reverse_transitions_fail(self):
        for case in ['source','output','record','extra_record','missing_record','same_version','other_file','reverse']:
            base=copy.deepcopy(self.base);runtime=copy.deepcopy(self.runtime)
            if case=='source':base['inventory']['files'][PARSER_PATH]='0'*64
            if case=='output':runtime['inventory']['files'][PARSER_PATH]='0'*64
            if case=='record':runtime['inventory']['generated_patches'][-1]['patch_id']='unreviewed'
            if case=='extra_record':runtime['inventory']['generated_patches'].append({'path':'odoo/http.py'})
            if case=='missing_record':runtime['inventory']['generated_patches']=[]
            if case=='same_version':runtime['native_manifests']['mp_compat']['version']='19.0.0.1.0'
            if case=='other_file':runtime['inventory']['files']['odoo/http.py']='3'*64
            if case=='reverse':base['inventory']['files'][PARSER_PATH]=TARGET_SHA256;runtime['inventory']['files'][PARSER_PATH]=SOURCE_SHA256
            with self.subTest(case=case),self.assertRaises(OperatorError):validate_core_upgrade(base,runtime,self.descriptor)

if __name__=='__main__':unittest.main()
