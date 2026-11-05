"""Independently stage and review the exact developer upgrade on the fresh realm."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).parent
WORK = ROOT / '.local/release-kit-core26-rehearsal'
PRIVATE = ROOT / '.local/g7-core26-developer-install'
REFERENCE = WORK / 'private/reference'
TARGET = REFERENCE / 'operator/target.json'
STORE = REFERENCE / 'operator/control'
CATALOG = WORK / 'private/catalog'
REVIEW = PRIVATE / 'upgrade'
TRUST = REVIEW / 'trust.json'
CLI = WORK / 'source/tools/modular.py'
sys.path[:0] = [str(WORK / 'source' / path) for path in ('tools', 'packages/platform_sdk')]
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import operator_observer


def load(path):
    return json.loads(path.read_bytes())


def create(path, value):
    with path.open('x', encoding='utf8') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def command(label, args, timeout=180):
    prefix = [sys.executable, '-I', str(CLI), '--config', str(TRUST)]
    with (REVIEW / (label + '.stdout')).open('xb') as out, (REVIEW / (label + '.stderr')).open('xb') as err:
        result = subprocess.run(prefix + args, stdout=out, stderr=err, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Inspect protected ' + label + ' diagnostics and actual state before continuation')
    return load(REVIEW / (label + '.stdout'))


resume = sys.argv[1:] == ['--resume-after-policy-refusal']
assert resume or not sys.argv[1:]
candidate = load(OUT / 'candidate-build.json')
initial = load(TARGET)
assert initial['generation'] == 4 and initial['image_id'] == candidate['dependency_base_image']
assert initial['project'] == 'mp-r0-r1release1c1f3b9c7a85'
assert load(REFERENCE / 'state.json')['phase'] == 'kit_backend_worker_reference_qualified'
store = OperatorStore(STORE)
with sqlite3.connect('file:' + store.database.as_posix() + '?mode=ro', uri=True) as database:
    assert not database.execute("SELECT 1 FROM operations WHERE state IN ('running','approved','recovery_required')").fetchall()
trust = load(REFERENCE / 'operator/trust.json')
examples = candidate['independently_reproduced_example_artifacts']
trust['generation'] += 1
trust['approved_digests'] = sorted(set(trust['approved_digests']) | {row['digest'] for row in examples})
if resume:
    assert load(TRUST) == trust and load(REVIEW / 'target-before.json') == initial
    assert not (REVIEW / 'register.stdout').exists()
    assert 'Solved release differs from the independently staged executable image' in (REVIEW / 'plan.stderr').read_text()
else:
    assert not REVIEW.exists()
    protect_directory(REVIEW)
    create(TRUST, trust)
    for example in examples:
        name, digest = example['example'], example['digest']
        artifact = str(PRIVATE / (name + '.mplug'))
        command('validate-' + name, ['plugin', 'validate', artifact, '--digest', digest])
        command('catalog-add-' + name, ['catalog', '--store', str(CATALOG), 'add', artifact, '--digest', digest])

validator = configuration(TRUST)
catalog = Catalog(CATALOG, validator, readonly=True)
snapshot = catalog.snapshot()
assert {row['digest'] for row in examples} <= {row['digest'] for row in snapshot}
observer = operator_observer(store, TARGET)
observation = observer.read()
before = observer.state(observation, snapshot)['state']
if resume:
    assert before == load(REVIEW / 'before.json')
else:
    create(REVIEW / 'before.json', before)
    create(REVIEW / 'target-before.json', initial)
targets = []
plugins = {'org.example.' + row['example'] for row in examples}
for row in before['installations']:
    if row['plugin_id'] in plugins:
        assert row['state'] == 'installed' and row['feature_state'] == 'enabled'
        targets.append({key: row[key] for key in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')}
                       | {'action': 'upgrade'})
assert len(targets) == 4 and {row['plugin_id'] for row in targets} == plugins
nomination = {'operation_type': 'upgrade', 'targets': targets}
if resume:
    assert load(REVIEW / 'nomination.json') == nomination
else:
    create(REVIEW / 'nomination.json', nomination)
validation = ['--deployment-config', str(TARGET), '--catalog', str(CATALOG)]
options = ['--store', str(STORE), *validation]
suffix = '-release-policy' if resume else ''
stage = command('stage' + suffix, ['plugin', 'stage-image', '--image-id', candidate['image_id'], *options])
assert (stage['base_image_id'], stage['target_image_id']) == (initial['image_id'], candidate['image_id'])
bundle = command('plan' + suffix, ['plugin', 'plan-staged', '--input', str(REVIEW / 'nomination.json'), *options])
assert {row['plugin_id'] for row in bundle['operation_lock']['targets']} == plugins
assert len(bundle['operation_lock']['targets']) == 4
assert bundle['operation_lock']['bindings'] == before['bindings']
assert bundle['operation_lock']['endpoints'] == before['endpoints']
assert bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
assert not bundle['plan']['destructive']
operation, plan_hash = bundle['plan']['operation_id'], bundle['plan_hash']
command('register', ['operations', '--store', str(STORE), 'register',
                     '--bundle', str(REVIEW / ('plan' + suffix + '.stdout')), *validation])
executor = StagedNativeExecutor(store, TARGET, CATALOG, validator)
create(REVIEW / 'independent-review.json', store.review(operation, executor._validate()))
assert load(TARGET) == initial
receipt = {'result': 'staged_and_independently_reviewed', 'operation_id': operation, 'plan_hash': plan_hash,
           'target_generation': initial['generation'], 'candidate_image': candidate['image_id'],
           'upgraded_plugins': sorted(plugins), 'scopes': len(targets), 'checkpoint_required': True,
           'no_permission_binding_or_endpoint_changes': True, 'deployment_changed': False}
create(OUT / 'review.json', receipt)
print(json.dumps(receipt))
