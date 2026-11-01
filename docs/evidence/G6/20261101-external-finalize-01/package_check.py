"""Reuse retained archive checks without rewriting their historical evidence."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).parent
if (OUT/'packages.json').exists():raise SystemExit('Preserve existing package evidence')
retained=ROOT/'docs/evidence/G6/20261101-notes-analysis-01/package_check.py'
scope=dict(__file__=__file__,__name__='current_connector_package_checks')
exec(compile(retained.read_text(),str(retained),'exec'),scope)
from packaging.specifiers import SpecifierSet
from jsonschema import Draft202012Validator
contracts=scope['module']
validator=Draft202012Validator(contracts.COMPUTED)
statistics=dict(characters=17,words=3,lines=2)
assert validator.is_valid(dict(statistics=statistics,authority_digest='sha256:'+'a'*64))
assert not validator.is_valid(statistics)
assert not validator.is_valid(dict(statistics=statistics,authority_digest='unvalidated'))
manifest=scope['assemble'](ROOT,'plugins/notes_stats/plugin.toml')[0]
compatibility=SpecifierSet(manifest['compatibility']['platform'])
assert '0.1.13' in compatibility and '0.1.12' not in compatibility
report=json.loads((OUT/'packages.json').read_text())
report.update(private_computed_schema_validated=True,minimum_platform='0.1.13',frozen_wire_contracts_changed=False,
    plugin_manifest_sha256=hashlib.sha256((ROOT/'plugins/notes_stats/plugin.toml').read_bytes()).hexdigest())
(OUT/'packages.json').write_text(json.dumps(report,indent=2)+'\n')
print('Private computed wrapper validates; source-only connector requires platform .13')
