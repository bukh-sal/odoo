"""Materialized clean-core TEST policy and actual worker inventory guard."""
import ast
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'tests')]
from build_distribution import build
from modular_platform import worker_start

POLICY='deploy/distribution-r1-clean-probe.json'
EXPECTED={'base','web','base_setup','auth_password_policy','bus','mp_compat','mp_identity','mp_core'}
BANNED=('tests/','tests\\','fixtures/','fixtures\\','applications/','examples/','plugins/',
        'services/','release/','artifacts/','tools/reference_operator/','packages/contracts/examples/',
        'packages/contracts/fixtures/')


class CleanCandidateMaterialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='mp-clean-candidate-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.target=Path(cls.temporary.name)/'release'
        cls.inventory=build(ROOT,cls.target,POLICY)

    def files(self):return {path.relative_to(self.target).as_posix() for path in self.target.rglob('*') if path.is_file()}
    def addons(self):
        found=[]
        for root in (self.target/'addons',self.target/'odoo/addons'):
            if root.is_dir():found.extend(path.name for path in root.iterdir() if (path/'__manifest__.py').is_file())
        return found

    def test_policy_is_clean_core_without_optional_packages(self):
        policy=json.loads((ROOT/POLICY).read_text(encoding='utf8'))
        self.assertEqual(set(policy['addons']),EXPECTED)
        self.assertEqual(policy['server_wide_modules'],['base','web'])
        self.assertEqual(policy['runtime_surface'],'clean')
        self.assertGreater(policy['stock_webclient'],False)
        self.assertNotIn('reference_packages',policy);self.assertNotIn('application_packages',policy)

    def test_current_identity_matches_emitted_core_and_historical_candidates_stay_readable(self):
        from modular_platform.projection import PLATFORM_VERSION,runtime_inputs
        from modular_platform.resolution import PlanningError
        from test_release_staging import staged_runtime
        manifest=ast.literal_eval((self.target/'addons/mp_core/__manifest__.py').read_text())
        self.assertEqual(manifest['version'],'19.0.'+PLATFORM_VERSION)
        cases=[(PLATFORM_VERSION,'19.0.'+PLATFORM_VERSION,True),
               (PLATFORM_VERSION,'19.0.0.1.49',False),
               ('0.1.53','19.0.0.1.53',True),('0.1.52','19.0.0.1.52',True),
               ('0.1.52','19.0.0.1.51',False),('0.1.51','19.0.0.1.51',True)]
        for platform,native,ok in cases:
            runtime=staged_runtime([]);runtime.update(platform_version=platform,native_manifests={'mp_core':{'version':native}})
            if ok:
                _,environment,provenance=runtime_inputs(runtime,[])
                self.assertEqual((environment['platform_version'],provenance['platform_version']),(platform,platform))
            else:
                with self.subTest(platform=platform,native=native),self.assertRaisesRegex(PlanningError,'platform/native core'):
                    runtime_inputs(runtime,[])

    def test_exact_tree_inventory_and_no_unshipped_paths(self):
        inventory=set(self.inventory['files']);files=self.files()
        self.assertEqual(files,inventory|{'distribution-inventory.json'})
        self.assertEqual(sorted(self.addons()),sorted(EXPECTED))
        self.assertFalse(set(self.addons()) & {'mp_shell','mp_example_notes','mp_discuss'})
        self.assertEqual(sorted(name for name in inventory if name.startswith('tools/')),['tools/start_worker.py'])
        self.assertEqual(self.inventory['files']['tools/start_worker.py'],hashlib.sha256((ROOT/'tools/start_worker.py').read_bytes()).hexdigest())
        for path in files:
            self.assertFalse(any(path.startswith(prefix) for prefix in BANNED),path)
        contract=set(name for name in files if name.startswith('packages/contracts/'))
        self.assertFalse(any(name.startswith('packages/contracts/examples/') or name.startswith('packages/contracts/fixtures/') for name in contract))
        self.assertTrue(all(name.startswith('packages/contracts/v1/') for name in contract))
        self.assertFalse(any(name.endswith('.mplug') for name in files))
        self.assertNotIn('artifacts',self.inventory)
        self.assertNotIn('reference_composition',self.inventory)
        self.assertNotIn('package_composition',self.inventory)
        self.assertFalse(any(name.startswith('odoo/addons/mp_example') for name in files))

    def test_injected_unselected_addon_or_host_file_is_detected_by_real_path_scan(self):
        inventory=set(self.inventory['files'])
        addon=self.target/'addons/mp_unexpected_probe';addon.mkdir()
        (addon/'__manifest__.py').write_text("{'name':'unexpected'}",encoding='utf8')
        leak=self.target/'tools/leak.py';leak.write_text('pass\n',encoding='utf8')
        files=self.files()
        self.assertIn('addons/mp_unexpected_probe/__manifest__.py',files)
        self.assertIn('tools/leak.py',files)
        self.assertNotIn('addons/mp_unexpected_probe/__manifest__.py',inventory)
        self.assertNotIn('tools/leak.py',inventory)
        self.assertNotEqual(files,inventory|{'distribution-inventory.json'})
        addon.joinpath('__manifest__.py').unlink();addon.rmdir();leak.unlink()

    def test_actual_worker_inventory_guard_accepts_clean_materialization_and_refuses_drift(self):
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def execute(self,sql,params=None):self.sql=' '.join(sql.split())
            def fetchone(self):
                if 'mp.active_inventory_digest' in self.sql:
                    return ('sha256:'+hashlib.sha256((self.root/'distribution-inventory.json').read_bytes()).hexdigest(),)
                return (None,)
            def fetchall(self):return []
        class Connection:
            def __init__(self,root):self.root=root
            def cursor(self):cur=Cursor();cur.root=self.root;return cur
        options={'db_name':'db','addons_path':'/opt/modular/addons','server_wide_modules':'base,web',
            'data_dir':'/var/lib/modular'}
        class Options(dict):
            def getint(self,key):return 0
            def getboolean(self,key):return False
            def get(self,key,default=''):return super().get(key,default)
            def getboolean(self,key):return False
        opts=Options(options);opts.getboolean=lambda key:False;opts.getint=lambda key:0
        digest='sha256:'+hashlib.sha256((self.target/'distribution-inventory.json').read_bytes()).hexdigest()
        self.assertEqual(worker_start.validate(self.target,opts,Connection(self.target),'db',digest),digest)
        target=self.target/'packages/contracts/v1/plan.schema.json';original=target.read_bytes()
        try:
            target.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError,'Application source differs'):
                worker_start.validate(self.target,opts,Connection(self.target),'db',digest)
        finally:
            target.write_bytes(original)


class CleanPolicyInputRefusals(unittest.TestCase):
    def test_unknown_surface_or_sdk_free_clean_materialization_refuses_without_output(self):
        for surface,sdk in (('cleen',True),('clean',False),('clean',1)):
            with tempfile.TemporaryDirectory(prefix='mp-clean-input-') as temporary:
                source=Path(temporary);policy=source/'policy.json';target=source/'output'
                policy.write_text(json.dumps({'runtime_surface':surface,'platform_sdk':sdk,'addons':[]}),encoding='utf8')
                with self.assertRaises(ValueError):build(source,target,'policy.json')
                self.assertFalse(target.exists())


if __name__=='__main__':
    unittest.main()
