"""Enumerate exact source inputs consumed by a curated distribution build."""
import json
from pathlib import Path
import sys
import tomllib

if __package__:
    from .source_layout import ENGINE, LAUNCHER, addon_source
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from source_layout import ENGINE, LAUNCHER, addon_source


def source_input_paths(root, policy_path):
    root = Path(root).resolve()
    if not isinstance(policy_path, (str, Path)):
        raise ValueError('Build policy path required')
    policy_path = (root / policy_path).resolve()
    if not policy_path.is_relative_to(root / 'deploy'):
        raise ValueError('Build policy must be operator-owned deploy input')
    policy = json.loads(policy_path.read_bytes())
    paths = set()

    def add(path):
        candidates = [path] if path.is_file() else path.rglob('*')
        for candidate in candidates:
            if candidate.is_file() and '__pycache__' not in candidate.parts and candidate.suffix != '.pyc':
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError('Build input escapes source checkout')
                paths.add(candidate.relative_to(root).as_posix())

    add(root / ENGINE)
    application_sources={}
    for relative in policy.get('application_packages',[]):
        # Recipes/resources may live outside the historical plugins directory.
        # Enumerate every explicit input; the assembler owns full recipe validation.
        def bound(name):
            if not isinstance(name,str):raise ValueError('Application source path required')
            path=root/name
            if not path.resolve().is_relative_to(root):raise ValueError('Application build input escapes checkout')
            return path
        recipe_file=bound(relative)
        recipe=tomllib.loads(recipe_file.read_text(encoding='utf8'))
        add(recipe_file)
        manifest_file=bound(recipe['manifest']);add(manifest_file)
        manifest=tomllib.loads(manifest_file.read_text(encoding='utf8'))
        addon=manifest['runtime']['addon_name']
        if addon in application_sources:raise ValueError('Duplicate application source addon')
        application_sources[addon]=bound(recipe['addon'])
        add(application_sources[addon])
        for name in recipe['resources'].values():add(bound(name))
    for name in policy['addons']:
        if not isinstance(name, str) or '/' in name or '\\' in name or name in ('.', '..'):
            raise ValueError('Invalid distribution addon name')
        add(application_sources[name] if name in application_sources else addon_source(root, name))
    for directory in ('plugins', 'packages/contracts', 'packages/platform_sdk', 'deploy', 'tools', 'tests/fixtures'):
        add(root / directory)
    for name in ('.dockerignore', 'LICENSE', 'COPYRIGHT', 'requirements.txt', LAUNCHER):
        add(root / name)
    return sorted(paths)
