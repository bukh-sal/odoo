"""G5 actual OS ACL/UID and crash-released process locks, not expiring leases."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.operator_os import (current_identity, protect_directory, verify_private_directory,
    OperatorError, ProcessLock, OperationLocks, LockBusy, LockFenced, _system_directory)


class OperatorOS(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.private = protect_directory(Path(self.temporary.name) / 'control')

    def test_identity_is_os_authenticated_and_private_acl_ignores_user_module_env(self):
        identity = current_identity()
        with patch.dict(os.environ, {'USERNAME': 'forged', 'USER': 'forged', 'SID': 'S-1-0-0', 'PSModulePath': str(self.private / 'nonexistent')}):
            self.assertEqual(current_identity(), identity)
            self.assertEqual(verify_private_directory(self.private), identity)
        self.assertTrue(identity.startswith('windows-sid:' if os.name == 'nt' else 'posix-uid:'))

    def test_existing_broad_directory_fails_closed_instead_of_resetting_permissions(self):
        if os.name == 'nt':
            program = str(_system_directory() / 'icacls.exe')
            subprocess.run([program, str(self.private), '/grant', '*S-1-1-0:(OI)(CI)R'], check=True, capture_output=True)
        else:
            os.chmod(self.private, 0o755)
        with self.assertRaises(OperatorError):
            verify_private_directory(self.private)
        with self.assertRaises(OperatorError):
            protect_directory(self.private)

    def test_second_handle_cannot_steal_and_persistent_file_survives_release(self):
        first = ProcessLock(self.private, 'deployment-fixture')
        with first:
            nonce = first.check()
            with self.assertRaises(LockBusy):
                with ProcessLock(self.private, 'deployment-fixture'):
                    self.fail('Duplicate lock acquired')
        self.assertTrue(first.path.is_file())
        with ProcessLock(self.private, 'deployment-fixture') as later:
            self.assertNotEqual(nonce, later.check())
        with self.assertRaises(LockFenced):
            first.check()

    def test_child_crash_releases_os_lock_without_lease_timeout_or_file_removal(self):
        child = """import sys,os
sys.path.insert(0,sys.argv[1])
from modular_platform.operator_os import ProcessLock
with ProcessLock(sys.argv[2],'crash-fixture'):
 print('LOCKED',flush=True)
 sys.stdin.buffer.read(1)
 os._exit(87)
"""
        process = subprocess.Popen([sys.executable, '-c', child, str(ROOT / 'packages/platform_sdk'), str(self.private)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'LOCKED')
            path = self.private / 'crash-fixture.lock'
            inode = path.stat().st_ino
            with self.assertRaises(LockBusy):
                with ProcessLock(self.private, 'crash-fixture'):
                    self.fail('Live child lock was stolen')
            process.stdin.write('x')
            process.stdin.flush()
            _, errors = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 87, errors)
            with ProcessLock(self.private, 'crash-fixture') as acquired:
                self.assertTrue(acquired.check())
                self.assertEqual(path.stat().st_ino, inode)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=15)

    def test_lock_loss_fences_further_work(self):
        with ProcessLock(self.private, 'fence-fixture') as locked:
            if os.name == 'posix':
                # Linux can rename a locked inode; its replacement must not count
                # as the original process-held lock. Both paths are private fixtures.
                moved = self.private / 'old-fence-fixture.lock'
                self.assertEqual(moved.parent.resolve(), self.private.resolve())
                locked.path.rename(moved)
                locked.path.write_bytes(b'\0')
                with self.assertRaises(LockFenced):
                    locked.check()
            else:
                # Windows denies deletion/rename of this open CRT handle. Closing
                # the owner descriptor is the supported loss-of-lock fault here.
                locked.file.close()
                with self.assertRaises(LockFenced):
                    locked.check()

    def test_deployment_lock_precedes_sites_and_failed_acquire_releases_partial_set(self):
        uid = lambda value: str(UUID(int=value))
        with OperationLocks(self.private, uid(10), [uid(30), uid(20)]) as first:
            self.assertEqual(len(first.check()), 3)
            self.assertTrue(first.locks[0].name.startswith('deployment-'))
            self.assertEqual([lock.name for lock in first.locks[1:]], ['site-' + uid(20), 'site-' + uid(30)])
            with self.assertRaises(LockBusy):
                with OperationLocks(self.private, uid(11), [uid(20)]):
                    self.fail('Shared database/site lock was stolen')
            with ProcessLock(self.private, 'deployment-' + uid(11)) as released_partial:
                self.assertTrue(released_partial.check())

    def test_links_and_unstructured_lock_names_are_rejected(self):
        for name in ('../escape', 'has space', 'Uppercase', 'x' * 101):
            with self.subTest(name=name):
                with self.assertRaises(OperatorError):
                    ProcessLock(self.private, name)
        if os.name == 'posix':
            link = self.private / 'linked.lock'
            link.symlink_to(self.private / 'outside')
            with self.assertRaises(OperatorError):
                ProcessLock(self.private, 'linked').acquire()


if __name__ == '__main__':
    unittest.main()
