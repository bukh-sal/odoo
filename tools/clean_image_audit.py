"""Verify a saved clean image's content-addressed final layers as data."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import PurePosixPath
import posixpath
import tarfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


class HashedReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.hash.update(data)
        return data


def checked(name):
    require(isinstance(name, str) and '\\' not in name and '\x00' not in name
        and '..' not in PurePosixPath(name).parts, 'Unsafe layer path')
    return '/' + str(PurePosixPath(name)).lstrip('/')


def audit_image(archive, image_id, inspection, expected_files, *, source_layers):
    """Reject old app bytes/whiteouts even when the merged root would hide them."""
    require(inspection['Id'] == image_id, 'Image inspection identity differs')
    actual_layers = inspection['RootFS']['Layers']
    require(source_layers and actual_layers[:len(source_layers)] != source_layers,
        'Source application image is a final ancestor')
    fixed = dict(User='10001:10001', WorkingDir='/opt/modular',
        Entrypoint=['/venv/bin/python', '/opt/modular/tools/start_worker.py'],
        Cmd=['-c', '/run/secrets/odoo_config'])
    for key, value in fixed.items():
        require(inspection['Config'].get(key) == value, 'Unexpected clean image startup: ' + key)
    expected = {'/opt/modular/' + name: digest for name, digest in expected_files.items()}
    directories = {'/opt/modular'}
    for name in expected:
        directories.update(str(p) for p in PurePosixPath(name).parents)
    seen = {}
    layers = []
    whiteouts = []
    with tarfile.open(archive) as outer:
        names = outer.getnames()
        require(len(set(names)) == len(names), 'Duplicate exported image member')

        def read_json(name):
            member = outer.getmember(name)
            require(member.isfile(), 'Image metadata must be a regular file')
            return json.load(outer.extractfile(member))

        def blob(descriptor):
            digest = descriptor['digest']
            require(digest.startswith('sha256:') and len(digest) == 71, 'Unsupported image digest')
            stream = outer.extractfile('blobs/sha256/' + digest[7:])
            raw = stream.read()
            require(len(raw) == descriptor['size'] and
                'sha256:' + hashlib.sha256(raw).hexdigest() == digest, 'Exported image blob changed')
            return raw

        index = read_json('index.json')
        roots = index['manifests']
        require(len(roots) == 1, 'Exactly one saved image required')
        root = roots[0]
        manifest_descriptor = root
        manifest = json.loads(blob(root))
        if 'manifests' in manifest:
            choices = [d for d in manifest['manifests']
                if d.get('platform', {}).get('os') == 'linux'
                and d.get('platform', {}).get('architecture') == inspection['Architecture']]
            require(len(choices) == 1, 'Exact saved image platform required')
            manifest_descriptor = choices[0]
            manifest = json.loads(blob(manifest_descriptor))
        config_descriptor = manifest['config']
        config = json.loads(blob(config_descriptor))
        require(image_id in (root['digest'], manifest_descriptor['digest'], config_descriptor['digest']),
            'Saved image is not the inspected immutable identity')
        require(config['architecture'] == inspection['Architecture'] and config['os'] == 'linux',
            'Saved image platform differs')
        require(config['rootfs']['diff_ids'] == actual_layers
            and len(manifest['layers']) == len(actual_layers), 'Saved final layer chain differs')
        for key in ('User', 'WorkingDir', 'Entrypoint', 'Cmd', 'Env'):
            require(config['config'].get(key) == inspection['Config'].get(key),
                'Saved image configuration differs: ' + key)
        for number, descriptor in enumerate(manifest['layers']):
            raw = blob(descriptor)
            stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if raw[:2] == b'\x1f\x8b' else io.BytesIO(raw)
            reader = HashedReader(stream)
            with tarfile.open(fileobj=reader, mode='r|') as layer:
                for entry in layer:
                    path = checked(entry.name)
                    require(path != '/source' and not path.startswith('/source/'),
                        'Build checkout leaked into final ancestry')
                    project = path == '/opt/modular' or path.startswith('/opt/modular/')
                    if '/.wh.' in path:
                        parent, name = posixpath.split(path)
                        affected = parent if name == '.wh..wh..opq' else posixpath.join(parent, name[4:])
                        require(not project and affected not in ('/', '/opt', '/opt/modular'),
                            'Project whiteout retains old application layers')
                        whiteouts.append(path)
                        continue
                    if entry.issym() or entry.islnk():
                        target = posixpath.normpath(entry.linkname if entry.islnk() or entry.linkname.startswith('/')
                            else posixpath.dirname(path) + '/' + entry.linkname)
                        target = checked(target)
                        require(not project and target != '/source' and not target.startswith('/source/')
                            and target != '/opt/modular' and not target.startswith('/opt/modular/'),
                            'Project source cannot be linked into final layers')
                    elif project and entry.isdir():
                        require(path in directories, 'Unexpected project directory in final layer: ' + path)
                    elif project:
                        require(entry.isfile() and path in expected,
                            'Unexpected project file in final layer: ' + path)
                        value = hashlib.file_digest(layer.extractfile(entry), 'sha256').hexdigest()
                        require(value == expected[path], 'Project layer bytes differ: ' + path)
                        seen[path] = value
            while reader.read(1024 * 1024):
                pass
            require('sha256:' + reader.hash.hexdigest() == actual_layers[number],
                'Uncompressed final layer digest differs')
            layers.append(dict(index=number, digest=descriptor['digest'], diff_id=actual_layers[number]))
    require(seen == expected, 'Final image is missing expected project files')
    with archive.open('rb') as stream:
        archive_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(result='exact-clean-final-layers-passed', image_id=image_id,
        source_image_not_final_ancestor=True, project_files=len(expected),
        layers=layers, non_project_whiteouts=whiteouts, image_tar_sha256=archive_digest)
