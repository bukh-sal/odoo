"""Enumerate exact source inputs consumed by a curated distribution build."""
import json
from pathlib import Path
import sys

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
    for name in policy['addons']:
        if not isinstance(name, str) or '/' in name or '\\' in name or name in ('.', '..'):
            raise ValueError('Invalid distribution addon name')
        add(addon_source(root, name))
    for directory in ('plugins', 'packages/contracts', 'packages/platform_sdk', 'deploy', 'tools', 'tests/fixtures'):
        add(root / directory)
    for name in ('.dockerignore', 'LICENSE', 'COPYRIGHT', 'requirements.txt', LAUNCHER):
        add(root / name)
    return sorted(paths)
