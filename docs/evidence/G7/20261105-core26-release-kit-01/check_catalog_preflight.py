"""Check the catalog guard at the boundary before fresh database mutation."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path.cwd()
OUT = Path(__file__).parent
WORK = ROOT / '.local/release-kit-core26-rehearsal'
KIT = ROOT / '.local/releases/r1-0.1.26'
PRIVATE = ROOT / '.local/g7-core26-catalog-guard'
sys.path.insert(0, str(ROOT / 'release'))
from initialize_reference import Reference, configuration, load
from modular_platform.artifacts import ArtifactError
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory


class MutationBoundary(Exception):
    pass


def before_database(_state, phase):
    assert phase == 'starting_empty_database'
    raise MutationBoundary


reference = Reference.__new__(Reference)
reference.state = lambda: {'phase': 'configured'}
reference.phase = before_database
reference.kit = KIT
reference.local = WORK / 'private/reference'
reference.private = protect_directory(PRIVATE)
trust = configuration(reference.local / 'operator/trust.json')
index = load(KIT / 'plugins/index.json')['packages']
try:
    reference.initialize()
except ArtifactError as error:
    assert 'Existing catalog required' in str(error)
else:
    raise AssertionError('Missing catalog guard did not refuse')

catalog = Catalog(PRIVATE / 'catalog', trust)
entry = index[0]
catalog.add(KIT / entry['file'], expected_digest=entry['digest'])
try:
    reference.initialize()
except ValueError as error:
    assert 'Import all reviewed reference kit archives' in str(error)
else:
    raise AssertionError('Incomplete catalog guard did not refuse')

reference.private = WORK / 'private'
try:
    reference.initialize()
except MutationBoundary:
    pass
else:
    raise AssertionError('Complete catalog did not reach the mutation boundary')

with (OUT / 'catalog-preflight.json').open('x', encoding='utf8') as handle:
    json.dump({
        'result': 'missing_and_incomplete_catalog_refused_before_mutation',
        'complete_catalog_reached_database_boundary': True, 'docker_commands': 0,
        'initializer_sha256': hashlib.sha256((ROOT / 'release/initialize_reference.py').read_bytes()).hexdigest(),
    }, handle, indent=2)
    handle.write('\n')
print('Catalog preflight passed on the extracted operator interpreter')
