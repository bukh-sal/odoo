"""Local OS identity, private directory and process-held executor locks."""
from __future__ import annotations

import csv
import ctypes
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from uuid import UUID, uuid4

from .contracts import ContractError


class OperatorError(ContractError):
    pass


class LockBusy(OperatorError):
    pass


class LockFenced(OperatorError):
    pass


def _system_directory():
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OperatorError('Windows system directory lookup failed')
    return Path(buffer.value)


def current_identity():
    """Read OS-authenticated identity; USER/USERNAME/SID env values are ignored."""
    if os.name == 'nt':
        completed = subprocess.run([str(_system_directory() / 'whoami.exe'), '/user', '/fo', 'csv', '/nh'],
                                   capture_output=True, text=True, timeout=10)
        rows = list(csv.reader(io.StringIO(completed.stdout)))
        if completed.returncode or len(rows) != 1 or len(rows[0]) != 2 or not re.fullmatch('S-1-[0-9-]+', rows[0][1]):
            raise OperatorError('OS-authenticated Windows SID lookup failed')
        return 'windows-sid:' + rows[0][1]
    if os.name == 'posix':
        return 'posix-uid:' + str(os.geteuid())
    raise OperatorError('Unsupported operator OS identity')


def _not_link(path):
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise OperatorError('Operator paths cannot traverse links or junctions')


def _windows_acl(path):
    # Do not inherit PowerShell7/user module discovery into the system Windows
    # PowerShell process (or permit user modules to replace OS security cmdlets).
    env = dict(os.environ, MP_OPERATOR_ACL_PATH=str(path),
               PSModulePath=str(_system_directory() / 'WindowsPowerShell/v1.0/Modules'))
    script = "$a=Get-Acl -LiteralPath $env:MP_OPERATOR_ACL_PATH; [pscustomobject]@{owner=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value;protected=$a.AreAccessRulesProtected;rules=@($a.Access | ForEach-Object {[pscustomobject]@{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;type=$_.AccessControlType.ToString();rights=[int]$_.FileSystemRights}})} | ConvertTo-Json -Depth 5 -Compress"
    powershell = _system_directory() / 'WindowsPowerShell/v1.0/powershell.exe'
    completed = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', script],
                               capture_output=True, text=True, env=env, timeout=15)
    if completed.returncode:
        raise OperatorError('Operator ACL inspection failed')
    try:
        return json.loads(completed.stdout)
    except ValueError as error:
        raise OperatorError('Invalid operator ACL observation') from error


def protect_directory(path):
    path = Path(path).absolute()
    _not_link(path)
    if path.exists():
        verify_private_directory(path)
        return path
    # Windows Python's mode0700 installs an explicit OWNER RIGHTS ACE. Start
    # empty with inherited parent protection, then install the exact DACL before
    # writing any control data. Existing directories are inspected, never reset.
    path.mkdir(mode=0o777 if os.name == 'nt' else 0o700, parents=True)
    if os.name == 'nt':
        sid = current_identity().removeprefix('windows-sid:')
        args = [str(_system_directory() / 'icacls.exe'), str(path), '/inheritance:r', '/grant:r']
        args.extend('*' + allowed + ':(OI)(CI)F' for allowed in (sid, 'S-1-5-18', 'S-1-5-32-544'))
        completed = subprocess.run(args, capture_output=True, timeout=15)
        if completed.returncode:
            raise OperatorError('Operator ACL protection failed')
    else:
        os.chmod(path, 0o700)
    verify_private_directory(path)
    return path


def verify_private_directory(path):
    path = Path(path).absolute()
    _not_link(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise OperatorError('Private operator directory required')
    identity = current_identity()
    if os.name == 'nt':
        acl = _windows_acl(path)
        sid = identity.removeprefix('windows-sid:')
        allowed = {sid, 'S-1-5-18', 'S-1-5-32-544'}
        if acl['owner'] != sid or acl['protected'] is not True or not acl['rules']:
            raise OperatorError('Operator ACL ownership/inheritance mismatch')
        if any(rule['sid'] not in allowed or rule['type'] != 'Allow' for rule in acl['rules']):
            raise OperatorError('Unexpected operator ACL access')
        if not any(rule['sid'] == sid and rule['rights'] & 0x1F01FF == 0x1F01FF for rule in acl['rules']):
            raise OperatorError('Operator owner needs full control of its private store')
    elif info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise OperatorError('Operator directory must be owned by the current UID and mode0700')
    return identity


class ProcessLock:
    """Persistent lock file, exclusive OS lock held until context exit/process death.

    No TTL, lease stealing, unlink-on-release or PID-only ownership claim. Acquire
    deployment lock first, then sorted site/database locks, and hold through all
    mutation/reconciliation work. A descriptor must not be shared across fork.
    """
    def __init__(self, directory, name):
        if not isinstance(name, str) or not re.fullmatch('[a-z0-9_-]{1,100}', name):
            raise OperatorError('Invalid structured process lock name')
        self.directory, self.name = Path(directory), name
        self.path = self.directory / (name + '.lock')
        self.file, self.pid, self.nonce = None, None, None
        self.held = False

    def acquire(self):
        if self.held:
            raise OperatorError('Process lock is already held by this handle')
        verify_private_directory(self.directory)
        _not_link(self.path)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        file = os.fdopen(descriptor, 'r+b', buffering=0)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode) or os.fstat(descriptor).st_nlink != 1:
                raise OperatorError('Lock must be a regular file with one filesystem link')
            if os.fstat(descriptor).st_size == 0:
                file.write(b'\0')
                os.fsync(descriptor)
            file.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, BlockingIOError) as error:
                raise LockBusy('Another executor holds the process lock; no takeover is allowed') from error
            self.file, self.pid, self.nonce, self.held = file, os.getpid(), str(uuid4()), True
            self.check()
            return self
        except BaseException:
            self.held, self.file = False, None
            file.close()
            raise

    def check(self):
        if not self.held or self.pid != os.getpid() or self.file is None or self.file.closed:
            raise LockFenced('Executor no longer owns its process lock')
        _not_link(self.path)
        try:
            opened, named = os.fstat(self.file.fileno()), self.path.stat()
        except OSError as error:
            raise LockFenced('Executor lock path disappeared') from error
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise LockFenced('Executor lock file was replaced; reconciliation required')
        return self.nonce

    def release(self):
        file, self.file, self.held = self.file, None, False
        if file is not None and not file.closed:
            try:
                if self.pid == os.getpid():
                    file.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
            finally:
                file.close()

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.release()


class OperationLocks:
    def __init__(self, directory, deployment_id, site_ids):
        if str(UUID(deployment_id)) != deployment_id or any(str(UUID(value)) != value for value in site_ids):
            raise OperatorError('Canonical deployment/site lock identities required')
        self.locks = [ProcessLock(directory, 'deployment-' + deployment_id)]
        self.locks.extend(ProcessLock(directory, 'site-' + value) for value in sorted(set(site_ids)))

    def check(self):
        return [lock.check() for lock in self.locks]

    def __enter__(self):
        try:
            for lock in self.locks:
                lock.acquire()
            return self
        except BaseException:
            for lock in reversed(self.locks):
                lock.release()
            raise

    def __exit__(self, *args):
        for lock in reversed(self.locks):
            lock.release()
