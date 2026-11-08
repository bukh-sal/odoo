"""Materialize native code from structurally validated application archive bytes.

This is a curated source-build helper, not the independently approved installer.
"""
import hashlib
import io
from pathlib import Path
import tempfile
import zipfile

from modular_platform.artifacts import ArtifactValidator, TrustPolicy


def materialize_archive(raw,staging):
    with tempfile.TemporaryDirectory(prefix='mp-build-archive-') as temporary:
        incoming=Path(temporary)/'input.mplug'
        incoming.write_bytes(raw)
        verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(incoming)
    manifest=verified.manifest
    if manifest['runtime']['kind']!='native':raise ValueError('Native application archive required')
    addon=manifest['runtime']['addon_name'];plugin=manifest['plugin']['id']
    target=Path(staging)/addon
    if target.exists() or target.is_symlink():raise ValueError('Duplicate or existing native package target')
    prefix='backend/odoo_addons/'+addon+'/'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for relative,digest in sorted(verified.inventory.items()):
            if not relative.startswith(prefix):continue
            destination=target/relative[len(prefix):]
            data=archive.read(plugin+'/'+relative)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Native archive source changed')
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as stream:stream.write(data)
    descriptor=dict(plugin_id=plugin,version=manifest['plugin']['version'],addon=addon,
                    digest=verified.digest,file=plugin+'-'+manifest['plugin']['version']+'.mplug')
    return descriptor,raw,target
