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
    OperatorError, ProcessLock, OperationLocks, LockBusy, LockFenced, _system_directory, _windows_acl)
import modular_platform.operator_os as operator_os


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
            before = _windows_acl(self.private)
        else:
            os.chmod(self.private, 0o755)
            before = os.stat(self.private).st_mode
        with self.assertRaises(OperatorError):
            verify_private_directory(self.private)
        with self.assertRaises(OperatorError):
            protect_directory(self.private)
        self.assertEqual(_windows_acl(self.private) if os.name == 'nt' else os.stat(self.private).st_mode, before)

    def test_fresh_directory_beneath_python_private_parent_is_normalized(self):
        if os.name != 'nt':
            self.skipTest('Windows ACL normalization is Windows-only')
        parent = Path(self.temporary.name)
        self.assertIn('S-1-3-4', {rule['sid'] for rule in _windows_acl(parent)['rules']})
        fresh = protect_directory(parent / 'fresh-control')
        acl = _windows_acl(fresh)
        sid = current_identity().removeprefix('windows-sid:')
        self.assertEqual(acl['owner'], sid)
        self.assertIs(acl['protected'], True)
        self.assertEqual({rule['sid'] for rule in acl['rules']},
                         {sid, 'S-1-5-18', 'S-1-5-32-544'})
        self.assertTrue(all(rule['type'] == 'Allow' for rule in acl['rules']))
        self.assertTrue(any(rule['sid'] == sid and rule['rights'] & 0x1F01FF == 0x1F01FF
                            for rule in acl['rules']))
        self.assertEqual(list(fresh.iterdir()), [])

    def test_existing_owner_rights_directory_is_refused_without_mutation(self):
        if os.name != 'nt':
            self.skipTest('Windows ACL normalization is Windows-only')
        existing = Path(self.temporary.name) / 'existing-owner-rights'
        existing.mkdir(mode=0o700)
        before = _windows_acl(existing)
        self.assertIn('S-1-3-4', {rule['sid'] for rule in before['rules']})
        with self.assertRaises(OperatorError):
            protect_directory(existing)
        self.assertEqual(_windows_acl(existing), before)

    def test_failed_acl_command_fails_closed_before_control_data(self):
        if os.name != 'nt':
            self.skipTest('Windows ACL command behavior is Windows-only')
        real_run = operator_os.subprocess.run
        for marker, label in (('/grant:r', 'grant'), ('/remove:g', 'remove')):
            with self.subTest(marker=marker):
                path = Path(self.temporary.name) / ('failed-' + label)
                seen = []
                def fail(args, *rest, **kwargs):
                    if isinstance(args, (list, tuple)) and 'icacls' in str(args[0]).lower():
                        seen.append(list(args))
                        if marker in args:
                            return subprocess.CompletedProcess(args, 1)
                    return real_run(args, *rest, **kwargs)
                with patch.object(operator_os.subprocess, 'run', side_effect=fail):
                    with self.assertRaises(OperatorError):
                        protect_directory(path)
                self.assertEqual(list(path.iterdir()), [])
                self.assertTrue(any(marker in command for command in seen))

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
