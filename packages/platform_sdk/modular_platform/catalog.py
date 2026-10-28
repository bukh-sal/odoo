"""Operator-owned immutable artifact catalog; never an application approval store."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from .artifacts import ArtifactError, ArtifactValidator


class Catalog:
    def __init__(self, root, validator: ArtifactValidator):
        self.root = Path(root)
        self.validator = validator
        if self.root.is_symlink():
            raise ArtifactError('Catalog root must not be a link')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.blobs = self.root / 'blobs'
        self.staging = self.root / 'staging'
        for path in (self.blobs, self.staging):
            if path.is_symlink():
                raise ArtifactError('Catalog directory must not be a link')
            path.mkdir(mode=0o700, exist_ok=True)
        self.database = self.root / 'catalog.sqlite3'
        if self.database.is_symlink():
            raise ArtifactError('Catalog database must not be a link')
        with self._connect() as database:
            database.execute('''CREATE TABLE IF NOT EXISTS artifacts (
                digest TEXT PRIMARY KEY, plugin_id TEXT NOT NULL, version TEXT NOT NULL,
                descriptor TEXT NOT NULL, quarantined INTEGER NOT NULL DEFAULT 0,
                UNIQUE(plugin_id, version))''')

    @contextmanager
    def _connect(self):
        database = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        database.row_factory = sqlite3.Row
        database.execute('PRAGMA synchronous=FULL')
        try:
            yield database
        finally:
            database.close()

    def path(self, digest):
        if not isinstance(digest, str) or not re.fullmatch('sha256:[0-9a-f]{64}', digest):
            raise ArtifactError('Invalid catalog digest')
        path = self.blobs / (digest[7:] + '.mplug')
        if path.is_symlink():
            raise ArtifactError('Catalog blob must not be a link')
        return path

    def add(self, source, *, expected_digest):
        # Private copy, trust, inventory, layout and extracted-byte validation all
        # precede publication. A failed operation cannot overwrite an existing blob.
        private, verified = self.validator.stage(source, self.staging, expected_digest=expected_digest)
        with private:
            descriptor = verified.descriptor()
            target = self.path(verified.digest)
            with self._connect() as database:
                database.execute('BEGIN IMMEDIATE')
                try:
                    row = database.execute('SELECT * FROM artifacts WHERE plugin_id=? AND version=?',
                                           (descriptor['plugin_id'], descriptor['version'])).fetchone()
                    if row and row['digest'] != verified.digest:
                        raise ArtifactError('Same plugin version is already associated with different artifact bytes')
                    if row and row['quarantined']:
                        raise ArtifactError('Artifact is quarantined')
                    if target.exists():
                        with target.open('rb') as stream:
                            actual = 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()
                        if actual != verified.digest:
                            raise ArtifactError('Existing catalog blob is corrupt; immutable bytes were preserved')
                    else:
                        # os.link is exclusive and atomically publishes a completely
                        # fsynced private file on this same filesystem. It does not
                        # interpret archive entries as filesystem links.
                        incoming = Path(private.name) / 'artifact.mplug'
                        os.link(incoming, target)
                        incoming.unlink()
                        os.chmod(target, 0o444)
                        self._sync_directory(self.blobs)
                    database.execute('INSERT OR IGNORE INTO artifacts (digest,plugin_id,version,descriptor) VALUES (?,?,?,?)',
                                     (verified.digest, descriptor['plugin_id'], descriptor['version'],
                                      json.dumps(descriptor, ensure_ascii=False, sort_keys=True)))
                    database.execute('COMMIT')
                except BaseException:
                    database.execute('ROLLBACK')
                    raise
            return descriptor

    @staticmethod
    def _sync_directory(path):
        if os.name == 'posix':
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def quarantine(self, digest):
        self.path(digest)
        with self._connect() as database:
            if database.execute('UPDATE artifacts SET quarantined=1 WHERE digest=?', (digest,)).rowcount != 1:
                raise ArtifactError('Unknown catalog artifact')

    def snapshot(self):
        with self._connect() as database:
            rows = database.execute('SELECT digest,quarantined FROM artifacts ORDER BY plugin_id,version').fetchall()
        result = []
        for row in rows:
            if row['quarantined']:
                continue
            # The current trust generation and actual bytes govern selection.
            # Publisher/provenance claims and saved descriptor JSON confer no trust.
            verified = self.validator.verify(self.path(row['digest']), expected_digest=row['digest'])
            result.append(verified.descriptor())
        return result
