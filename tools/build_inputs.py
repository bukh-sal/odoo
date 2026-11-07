"""Enumerate exact source inputs consumed by a curated distribution build."""
import json
from pathlib import Path


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

    # The builder excludes the native fixture collection from the engine copy.
    for path in (root / 'odoo').iterdir():
        if path.name != 'addons':
            add(path)
    for name in policy['addons']:
        if not isinstance(name, str) or '/' in name or '\\' in name or name in ('.', '..'):
            raise ValueError('Invalid distribution addon name')
        choices = [root / folder / name for folder in ('odoo/addons', 'addons', 'platform_addons', 'applications')]
        matches = [p for p in choices if (p / '__manifest__.py').is_file()]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous build source addon: ' + name)
        add(matches[0])
    for directory in ('plugins', 'packages/contracts', 'packages/platform_sdk', 'deploy', 'tools', 'tests/fixtures'):
        add(root / directory)
    for name in ('.dockerignore', 'LICENSE', 'COPYRIGHT', 'requirements.txt', 'odoo-bin'):
        add(root / name)
    return sorted(paths)
