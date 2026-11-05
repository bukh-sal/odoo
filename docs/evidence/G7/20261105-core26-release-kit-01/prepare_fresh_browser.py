"""Bind the existing owned browser profile to the fresh kit reference."""
import json
from pathlib import Path
import sys

ROOT = Path.cwd()
WORK = ROOT / '.local/release-kit-core26-rehearsal'
REFERENCE = WORK / 'private/reference'
OUT = ROOT / '.local/g7-core26-fresh-browser'
sys.path.insert(0, str(WORK / 'source/packages/platform_sdk'))
from modular_platform.operator_os import protect_directory, verify_private_directory


def load(path):
    return json.loads(path.read_bytes())


state = load(REFERENCE / 'state.json')
assert state['phase'] == 'kit_backend_worker_reference_qualified'
target = load(REFERENCE / 'operator/target.json')
assert target['project'] == state['project'] and target['image_id'] == state['image_id']
fixture = load(REFERENCE / 'fixtures.json')
checks = load(REFERENCE / 'reference-checks.json')
assert checks['phase'] == 'passed' and len(checks['notes']) == 2
profile = Path(load(ROOT / '.local/g7-ui-core26-01/browser-input.json')['profile'])
assert profile.resolve() == (ROOT / '.local/g7-ui-qualification-01/profile').resolve()
verify_private_directory(profile)
assert not OUT.exists()
protect_directory(OUT)
protect_directory(OUT / 'browser')
record = {
    'base': state['url'], 'database': state['database'], 'project': state['project'],
    'image_id': state['image_id'], 'inventory_digest': state['inventory_digest'],
    'generation': target['generation'], 'fixture': fixture,
    'password_file': str(REFERENCE / 'account-passwords.json'), 'actor': 'alice',
    'profile': str(profile), 'note_id': checks['notes']['A']['id'],
}
for path, value in [(OUT / 'browser-input.json', record), (OUT / 'tables-before.json', {})]:
    with path.open('x', encoding='utf8') as handle:
        json.dump(value, handle, indent=2)
print(json.dumps({'result': 'fresh_reference_browser_ready', 'project': state['project'],
                  'generation': target['generation']}))
