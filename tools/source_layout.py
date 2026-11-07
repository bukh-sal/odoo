"""Owned source locations, separate from the materialized runtime layout."""
from pathlib import Path
import re

ENGINE = Path('engine/odoo')
LAUNCHER = Path('engine/odoo-bin')
ADDON_ROOTS = ('framework_addons', 'applications', 'examples')
TEST_ADDONS = 'tests/addons'


def addon_source(root, name, *, include_tests=False):
    root = Path(root).resolve()
    if not isinstance(name, str) or not re.fullmatch('[a-z][a-z0-9_]*', name):
        raise ValueError('Invalid native addon name')
    directories = ADDON_ROOTS + ((TEST_ADDONS,) if include_tests else ())
    matches = [root / directory / name for directory in directories
               if (root / directory / name / '__manifest__.py').is_file()]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous owned source addon: ' + name)
    if not matches[0].resolve().is_relative_to(root):
        raise ValueError('Native source escapes owned checkout')
    return matches[0]
