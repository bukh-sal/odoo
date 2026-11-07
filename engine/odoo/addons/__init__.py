# Part of Odoo. See LICENSE and COPYRIGHT. Owned namespace bootstrap.
"""Native addon namespace for owned source and materialized installations."""
from pathlib import Path

# Source checkout: base belongs to framework services. Installed images place
# base beside this file; additional installed roots are supplied by config.
_framework = Path(__file__).resolve().parents[3] / 'framework_addons'
if (_framework / 'base/__manifest__.py').is_file():
    __path__.append(str(_framework))
del _framework
