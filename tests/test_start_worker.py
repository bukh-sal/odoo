"""Default startup never imports native code before independent pin checks."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
import start_worker
from modular_platform.worker_start import validate_data_addons
import test_workers


class DefaultStartupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        (self.root/'startup-profile').write_text('r1\n')
        self.guard=self.root/'packages/platform_sdk/modular_platform/worker_start.py'
        self.guard.parent.mkdir(parents=True);self.guard.write_text("raise RuntimeError('not imported before pin checks')")
        self.inventory={'policy':{'platform_sdk':True},'files':{self.guard.relative_to(self.root).as_posix():hashlib.sha256(self.guard.read_bytes()).hexdigest()}}
        self.publish_inventory()
        self.addCleanup(patch.stopall)
        patch.object(start_worker,'ROOT',self.root).start()
        patch.object(sys,'argv',['start_worker','-c','/run/secrets/odoo_config']).start()
        patch.dict(os.environ,{'MP_EXPECTED_DATABASE':'fixed_database','MP_EXPECTED_INVENTORY_DIGEST':self.pin},clear=True).start()

    def publish_inventory(self):
        raw=json.dumps(self.inventory).encode();(self.root/'distribution-inventory.json').write_bytes(raw)
        self.pin='sha256:'+hashlib.sha256(raw).hexdigest()

    def test_pins_and_fixed_arguments_checked_before_sdk_execution(self):
        with patch.object(start_worker.runpy,'run_path') as run:
            for key in ['MP_EXPECTED_DATABASE','MP_EXPECTED_INVENTORY_DIGEST']:
                with patch.dict(os.environ,{key:''}),self.assertRaisesRegex(ValueError,'pins are required'):start_worker.main()
            for args in [[],['--init','base'],['-c','other'],['-c','/run/secrets/odoo_config','-u','all'],['shell']]:
                with patch.object(sys,'argv',['start_worker',*args]),self.assertRaisesRegex(ValueError,'fixed configuration'):start_worker.main()
            with patch.dict(os.environ,{'MP_EXPECTED_INVENTORY_DIGEST':'sha256:'+'0'*64}),self.assertRaisesRegex(ValueError,'pin mismatch'):start_worker.main()
            run.assert_not_called()

    def test_verified_guard_receives_exact_independent_pins(self):
        calls=[]
        with patch.object(start_worker.runpy,'run_path',return_value={'main':lambda:calls.append(sys.argv[:])}) as run:
            start_worker.main()
            self.assertEqual(run.call_args.kwargs,{'run_name':'verified_worker_bootstrap'})
        self.assertEqual(calls,[['verified_worker_bootstrap','fixed_database',self.pin]])

    def test_inventory_cannot_downgrade_image_profile_or_bless_modified_guard(self):
        self.inventory['policy']['platform_sdk']=False;self.publish_inventory()
        with patch.dict(os.environ,{'MP_EXPECTED_INVENTORY_DIGEST':self.pin}),self.assertRaisesRegex(ValueError,'requires its SDK'):start_worker.main()
        self.inventory['policy']['platform_sdk']=True;self.publish_inventory();self.guard.write_text('modified')
        with patch.dict(os.environ,{'MP_EXPECTED_INVENTORY_DIGEST':self.pin}),self.assertRaisesRegex(ValueError,'bootstrap source differs'):start_worker.main()

    def test_baseline_keeps_native_arguments(self):
        (self.root/'startup-profile').write_text('baseline\n')
        with patch.object(sys,'argv',['start_worker','-i','base']),patch.object(start_worker.os,'execv') as execute:
            start_worker.main()
            execute.assert_called_once_with('/venv/bin/python',['/venv/bin/python','odoo-bin','-i','base'])

    def test_writable_addons_empty_directories_only(self):
        data=self.root/'data';addons=data/'addons/19.0';addons.mkdir(parents=True)
        validate_data_addons(data)
        for name in ['injected.py','injected.pyc','__pycache__/injected.cpython-312.pyc']:
            path=addons/name;path.parent.mkdir(exist_ok=True);path.write_bytes(b'not executable during check')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'writable data-dir'):validate_data_addons(data)
            path.unlink()


class AdditionalSourceTests(unittest.TestCase):
    setUp=test_workers.BootstrapTests.setUp
    run_validation=test_workers.BootstrapTests.run_validation
    def test_bytecode_in_any_executable_root_is_rejected(self):
        for name in ['addons/test_guard/injected.pyc','addons/test_guard/__pycache__/injected.cpython-312.pyc',
            'odoo/injected.pyc','packages/injected.pyc']:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'executable bytecode must be inventoried')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'search-path content'):self.run_validation()
            path.unlink()

    @unittest.skipIf(os.name=='nt','Real Linux symlink probes qualify runtime policy')
    def test_source_and_data_symlinks_rejected(self):
        link=self.root/'addons/alias';link.symlink_to(self.root/'addons/test_guard',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'source symlink'):self.run_validation()
        data=self.root/'data';data.mkdir();(data/'addons').symlink_to(self.root/'addons',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'writable data-dir'):validate_data_addons(data)


if __name__=='__main__':unittest.main()
