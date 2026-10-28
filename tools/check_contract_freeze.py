"""Fail on unreviewed drift in frozen public contract files."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / 'docs/contracts/freeze-v1.json'


def main():
    inventory = json.loads(INVENTORY.read_text())
    errors = []
    for name, expected in inventory['files'].items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(name)
    expected_schemas = {name for name in inventory['files'] if name.startswith('packages/contracts/')}
    actual_schemas = {p.relative_to(ROOT).as_posix() for p in (ROOT/'packages/contracts').rglob('*') if p.is_file()}
    errors.extend(sorted(actual_schemas ^ expected_schemas))
    if errors:
        print(json.dumps({'result':'failed','changed_contract_files':errors,'action':'ADR/version/fixtures/inventory and affected gate requalification required'}))
        return 1
    print(json.dumps({'result':'passed','contract_major':1,'files':len(inventory['files']),'rows':len(inventory['contracts'])}))
    return 0


if __name__ == '__main__': sys.exit(main())
