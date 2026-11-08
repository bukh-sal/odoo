"""Deterministic archive encoding shared by trusted local source assemblers.

This writes bytes; the existing ArtifactValidator still owns archive admission.
"""
import hashlib
import io
import json
import stat
import zipfile


def finish_archive(manifest, source_files, *, builder, provenance_extra=None):
    files = dict(source_files)
    provenance = dict(schema_version=1, builder=builder, trusted_inputs_only=True,
                      source_files={name: hashlib.sha256(data).hexdigest()
                                    for name, data in sorted(files.items())})
    provenance.update(provenance_extra or {})
    files['provenance.json'] = (json.dumps(provenance, sort_keys=True, indent=2)+'\n').encode()
    inventory = dict(schema_version=1, excluded=['inventory.json'],
                     files={name: hashlib.sha256(data).hexdigest()
                            for name, data in sorted(files.items())})
    files['inventory.json'] = (json.dumps(inventory, sort_keys=True, indent=2)+'\n').encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(manifest['plugin']['id']+'/'+name, (2000, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (stat.S_IFREG | 0o444) << 16
            archive.writestr(entry, data)
    return manifest, output.getvalue(), files
