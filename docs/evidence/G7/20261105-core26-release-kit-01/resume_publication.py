"""Complete publication after the fresh core provision stopped at catalog open."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).parent
WORK = ROOT / '.local/release-kit-core26-rehearsal'
SOURCE = WORK / 'source'
KIT = ROOT / '.local/releases/r1-0.1.26'
sys.path.insert(0, str(SOURCE / 'release'))
from initialize_reference import Reference, load
from modular import configuration
from modular_platform.catalog import Catalog

reference = Reference(argparse.Namespace(kit=KIT, workdir=WORK))
state = reference.state()
project = 'mp-r0-r1release1c1f3b9c7a85'
assert state['project'] == project and state['phase'] == 'publishing_core_bootstrap'
assert state['image_id'] == 'sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415'
assert not (reference.local / 'operator/target.json').exists()
assert not (reference.local / 'logs/bootstrap-release-pins.stdout').exists()
assert not (reference.private / 'catalog').exists()
for step in ('core-init', 'core-provision'):
    name = project + '-' + step
    observed = json.loads(subprocess.check_output(['docker', 'inspect', name], timeout=30))[0]
    assert observed['State']['Status'] == 'exited' and observed['State']['ExitCode'] == 0
    assert observed['Image'] == state['image_id']
    assert observed['Config']['Labels']['com.modular.disposable'] == project
counts = reference.sql(state, 'reconcile-before-publication', """
    BEGIN READ ONLY;
    SELECT jsonb_build_array(
        (SELECT count(*) FROM mp_workspace),
        (SELECT count(*) FROM mp_plugin_installation),
        (SELECT count(*) FROM ir_config_parameter
         WHERE key IN ('mp.release_digest', 'mp.active_inventory_digest')));
    ROLLBACK;
""")
assert json.loads(counts) == [2, 0, 0]
fixtures = load(reference.local / 'fixtures.json')
assert sorted(fixtures['workspaces']) == ['A', 'B'] and not fixtures['installed_plugins']

trust_path = KIT / 'plugins/curated-trust.json'
assert trust_path.read_bytes() == (reference.local / 'operator/trust.json').read_bytes()
catalog_path = reference.private / 'catalog'
index = load(KIT / 'plugins/index.json')['packages']
for number, row in enumerate(index):
    reference.command(f'import-kit-catalog-{number:02d}', [
        sys.executable, '-I', str(SOURCE / 'tools/modular.py'), '--config', str(trust_path),
        'catalog', '--store', str(catalog_path), 'add', str(KIT / row['file']), '--digest', row['digest'],
    ])
catalog = Catalog(catalog_path, configuration(trust_path), readonly=True)
assert {row['digest'] for row in catalog.snapshot()} == {row['digest'] for row in index}
assert len(index) == 19
with (OUT / 'catalog-and-publication-reconciliation.json').open('x', encoding='utf8') as handle:
    json.dump({
        'project': project, 'initial_phase': state['phase'], 'catalog_imported': len(index),
        'counts_before_publication': json.loads(counts),
        'provisioning_receipt_sha256': hashlib.sha256((reference.local / 'fixtures.json').read_bytes()).hexdigest(),
        'core_helpers_exited_zero': True, 'bootstrap_target_previously_absent': True,
    }, handle, indent=2)
    handle.write('\n')
reference.publish(state)
