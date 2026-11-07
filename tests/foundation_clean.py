"""Rehearse the consumer kit with its own offline interpreter and source only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/foundation-release'
WORK = LOCAL / 'clean-core46'
KIT = ROOT / '.local/releases/foundation-r1-core46'


def main():
    setup = json.loads((WORK / 'operator-setup.json').read_bytes())
    selected, source = Path(setup['python']), Path(setup['source'])
    assert selected.resolve().is_relative_to(WORK) and source.resolve() == WORK / 'source'
    receipt = LOCAL / 'clean-provision.json'
    assert not receipt.exists(), 'Inspect the consumer phase/journal before another attempt'
    record = dict(phase='starting', source_commit=setup['source_commit'], started_utc=datetime.now(timezone.utc).isoformat())
    def phase(name, command):
        record['phase'] = name
        receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
        print(json.dumps(dict(phase=name)), flush=True)
        log = LOCAL / ('clean-' + name + '.log')
        with log.open('xb') as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=900)
    script = '''
from pathlib import Path
import sys,json
root,kit,work=map(Path,sys.argv[1:])
sys.path[:0]=[str(root/'tools'),str(root/'packages/platform_sdk')]
from modular import configuration
from modular_platform.catalog import Catalog
assert not (work/'private/catalog').exists()
catalog=Catalog(work/'private/catalog',configuration(kit/'plugins/curated-trust.json'))
for row in json.loads((kit/'plugins/index.json').read_bytes())['packages']:
    catalog.add(kit/row['file'],expected_digest=row['digest'])
print(json.dumps(dict(imported=len(catalog.snapshot()),copied_existing_catalog=False)))
'''
    phase('catalog', [str(selected), '-I', '-c', script, str(source), str(KIT), str(WORK)])
    prefix = [str(selected), '-I', str(source / 'release/initialize_reference.py')]
    common = ['--kit', str(KIT), '--workdir', str(WORK)]
    phase('prepare', prefix + ['prepare', *common, '--reference-fixture', '--port', '18132',
                               '--subnets', '10.203.156.64/28', '10.203.156.80/28'])
    phase('initialize', prefix + ['initialize', *common, '--native-app', 'maintenance'])
    phase('install', prefix + ['install', *common])
    phase('walkthrough', [str(selected), '-I', str(source / 'release/check_reference.py'), *common])
    record.update(phase='verified', finished_utc=datetime.now(timezone.utc).isoformat(),
                  isolated_kit_operator=True, native_app='maintenance', no_global_toolchain_changes=True)
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
