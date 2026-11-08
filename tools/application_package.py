"""Assemble reviewed native application sources as data, with no build hooks.

Local recipe v1 is an authoring input, never an installation or trust grant.
The recipe supplies manifest, addon directory, and explicit archive resources.
All paths are portable and relative to one selected checkout. Schema, ABI and
source ownership validation remain separate from operator digest approval.
"""
import ast
from pathlib import Path
import tempfile
import tomllib

from modular_platform.artifacts import ArchiveLimits, ArtifactValidator, TrustPolicy, portable_path
from modular_platform.contracts import normalize_manifest, native_version
from package_archive import finish_archive


def source_path(root, relative):
    portable_path(relative)
    current = root
    for part in relative.split('/'):
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise ValueError('Linked application source is not supported')
    if not current.resolve().is_relative_to(root):
        raise ValueError('Application source escapes the selected checkout')
    return current


def assemble_application(source, recipe_path):
    root = Path(source).resolve(strict=True)
    recipe_file = source_path(root, recipe_path)
    limits = ArchiveLimits()
    if recipe_file.stat().st_size > limits.metadata:
        raise ValueError('Oversized authoring recipe')
    recipe = tomllib.loads(recipe_file.read_text(encoding='utf8'))
    if (set(recipe) != {'schema_version', 'manifest', 'addon', 'resources'}
            or type(recipe['schema_version']) is not int or recipe['schema_version'] != 1
            or not isinstance(recipe['resources'], dict)):
        raise ValueError('Unsupported application authoring recipe')
    files = {}
    total = 0

    def add(name, path):
        nonlocal total
        portable_path(name)
        if name in files or name in {'inventory.json', 'provenance.json'}:
            raise ValueError('Duplicate or reserved application archive path')
        if not path.is_file() or path.stat().st_size > limits.per_file:
            raise ValueError('Missing, special or oversized application source')
        with path.open('rb') as stream:
            data = stream.read(limits.per_file+1)
        total += len(data)
        if len(data) > limits.per_file or total > limits.expanded or len(files) >= limits.entries-2:
            raise ValueError('Application source exceeds archive limits')
        files[name] = data

    add('plugin.toml', source_path(root, recipe['manifest']))
    manifest = normalize_manifest(tomllib.loads(files['plugin.toml'].decode('utf8')))
    if manifest['runtime']['kind'] != 'native':
        raise ValueError('This authoring recipe supports native applications only')
    addon = manifest['runtime']['addon_name']
    directory = source_path(root, recipe['addon'])
    if not directory.is_dir() or directory.name != addon:
        raise ValueError('Explicit addon directory must match the manifest addon name')
    native_file = source_path(root, recipe['addon']+'/__manifest__.py')
    if native_file.stat().st_size > limits.metadata:
        raise ValueError('Oversized native manifest')
    native = ast.literal_eval(native_file.read_text(encoding='utf8'))
    if native.get('version') != native_version(manifest['plugin']['version']):
        raise ValueError('Application and native versions must agree')
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(root).as_posix()
        checked = source_path(root, relative)
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if checked.is_dir():
            continue
        add('backend/odoo_addons/'+addon+'/'+path.relative_to(directory).as_posix(), checked)
    for destination, relative in recipe['resources'].items():
        if destination == 'plugin.toml' or destination.startswith('backend/'):
            raise ValueError('Resources cannot replace application code or manifest')
        add(destination, source_path(root, relative))
    if not any(name.startswith('notices/') for name in files):
        raise ValueError('Explicit application license/attribution notices required')
    result = finish_archive(manifest, files, builder='owned-application-assembler-v1')
    # Development mode checks bytes without claiming or recording curated trust.
    with tempfile.TemporaryDirectory(prefix='mp-application-check-') as temporary:
        candidate = Path(temporary)/'candidate.mplug'
        candidate.write_bytes(result[1])
        ArtifactValidator(TrustPolicy('development', allow_unsigned_development=True)).verify(candidate)
    return result
