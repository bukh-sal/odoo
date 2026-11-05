"""Verify the installed UI samples and retire the exact completed helpers."""
import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import maintain as maintenance
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner

out = Path(__file__).parent
root = maintenance.ROOT
run_root = root / '.local/g7-ui-core25-01'
state = maintenance.load(maintenance.PRIVATE / 'state.json')
native = maintenance.context()
assert state['phase'] == 'preserved_core25_needs_HTTP_UI09'
assert native.config['generation'] == 6

metrics = {}
for mode in ('baseline', 'zoom200'):
    run = run_root / mode
    audit = maintenance.load(run / 'observations.json')
    assert audit['image'] == state['image_id'] and audit['generation'] == 6
    assert not audit['runtime_exceptions'] and not audit['foreign_requests']
    findings = audit['findings']
    # The CSS text-color sampler includes the icon-only button. The separate
    # screenshot measurement below evaluates its actual visible strokes.
    assert findings == ([{'check': 'dark-native-modal', 'text': '', 'ratio': 1.436, 'required': 4.5}]
                        if mode == 'baseline' else [])
    by_name = {row['name']: row['data'] for row in audit['observations']}
    for theme in ('light', 'dark'):
        dialog = by_name[theme + '-native-modal-keyboard']
        assert dialog['modalAX'] == [{'role': 'dialog', 'name': 'Delete note', 'ignored': False}]
        assert all(item['inside_modal'] for item in dialog['cycle'])
        assert dialog['restored']['name'] == 'Delete note'
    metrics[mode] = {key: by_name[key] for key in ('actual_window_zoom_metrics', 'Arabic-window-metrics')}
    for sample in metrics[mode].values():
        assert sample['scroll_width'] == sample['root_width'] == (628 if mode == 'zoom200' else 1256)
        assert sample['dpr'] == (2 if mode == 'zoom200' else 1)
    assert metrics[mode]['Arabic-window-metrics']['dir'] == 'rtl'

glyphs = maintenance.load(out / 'close-glyph-contrast.json')
for glyph in glyphs:
    image = run_root / 'baseline' / (glyph['theme'] + '-confirm.png')
    assert hashlib.sha256(image.read_bytes()).hexdigest() == glyph['screenshot_sha256']
    assert glyph['pixels_at_least_3_to_1'] >= 8

narrow = maintenance.load(run_root / 'narrow/observations.json')
assert len(narrow['samples']) == 3 and not any(narrow[key] for key in ('overflow', 'foreign', 'exceptions'))
for mode in ('baseline', 'zoom200', 'narrow'):
    process = maintenance.load(run_root / mode / 'process.json')
    assert process['state'] == 'stopped' and process['exit'] == {'code': 0, 'signal': None}
profile = Path(maintenance.load(run_root / 'browser-input.json')['profile'])
partition = maintenance.load(profile / 'Default/Preferences').get('partition', {})
for key, prior in maintenance.load(run_root / 'zoom-before.json')['keys'].items():
    assert (key in partition) == prior['existed'] and partition.get(key) == prior['value']

assert maintenance.snapshot('data-after-UI25', native) == maintenance.load(maintenance.PRIVATE / 'data-after.json')
assert maintenance.worker(native) == maintenance.load(maintenance.PRIVATE / 'worker-before.json')

operation = state['operation_id']
helpers = subprocess.check_output(
    ['docker', 'ps', '-aq', '--filter', 'label=com.modular.operation=' + operation],
    text=True, timeout=30
).splitlines()
assert len(helpers) == 7
old_app = maintenance.load(maintenance.PRIVATE / 'target-before.json')['worker_id']
rows = json.loads(subprocess.check_output(['docker', 'inspect', *helpers, old_app], timeout=30))
logs = protect_directory(maintenance.PRIVATE / 'retired-diagnostics')
expected_helpers = {'checkpoint', 'native', 'metadata', 'assets', 'dispatch-fence', 'dispatch-reconcile', 'dispatch-enable'}
retire = []
for row in rows:
    assert row['Id'] != native.config['worker_id']
    assert row['State']['Status'] == 'exited' and row['State']['ExitCode'] == 0
    if row['Id'] == old_app:
        assert row['Image'] == state['base_image']
        assert row['Config']['Labels']['com.docker.compose.project'] == native.config['project']
    else:
        prefix = '/' + native.config['project'] + '-op-' + operation + '-'
        assert row['Name'].startswith(prefix)
        assert row['Config']['Labels']['com.modular.operation'] == operation
        expected_helpers.remove(row['Name'][len(prefix):])
    if row['HostConfig']['LogConfig']['Type'] != 'none':
        result = subprocess.run(['docker', 'logs', row['Id']], capture_output=True, timeout=30, check=True)
        for extension, stream in [('stdout', result.stdout), ('stderr', result.stderr)]:
            with (logs / (row['Id'] + '.' + extension)).open('xb') as handle:
                handle.write(stream)
    retire.append({'id': row['Id'], 'name': row['Name'], 'image': row['Image']})
assert not expected_helpers

values = {key: base64.b64decode(value) for key, value in maintenance.load(
    maintenance.REFERENCE / 'qualification-known-values-worker.json').items()}
scanner = Scanner((root / '.local/g5-secret-scan/fingerprint-key').read_bytes(), values)
excluded = {'data-before.stdout', 'data-after-review.stdout', 'data-after.stdout',
            'data-before-UI25.stdout', 'data-after-UI25.stdout'}
streams = [file for folder in (maintenance.PRIVATE, logs) for file in folder.iterdir()
           if file.is_file() and file.suffix in ('.stdout', '.stderr', '.log') and file.name not in excluded]
evidence = [file for file in out.iterdir() if file.is_file()]
for mode in ('baseline', 'zoom200', 'narrow'):
    folder = run_root / mode
    evidence += [folder / 'observations.json', *folder.glob('*.png'), *folder.glob('network.json')]
findings = [item for file in streams + evidence for item in scanner.inspect_file(file, str(file.relative_to(root)))]
assert not findings, 'Review findings in protected diagnostic inputs before publishing'

for mode in ('baseline', 'zoom200', 'narrow'):
    destination = out / mode
    destination.mkdir()
    for name in ('observations.json', 'network.json', 'light-confirm.png', 'dark-confirm.png', 'Arabic-settings.png'):
        file = run_root / mode / name
        if file.is_file():
            shutil.copyfile(file, destination / name)
maintenance.create(out / 'installed-observations.json', {
    'image': state['image_id'], 'generation': 6, 'operation': operation,
    'ui09': 'partial_installed_evidence',
    'dialog_name_both_themes_and_zoom_levels': 'Delete note',
    'glyph_contrast': glyphs, 'zoom_metrics': metrics, 'narrow': narrow['samples'],
    'tables_exact_after_read_only_ui': 17, 'worker_preserved': True,
    'browser_runs_closed': 3, 'zoom_preferences_restored': True,
    'privacy': {'known_values': len(values), 'streams': len(streams), 'evidence_files': len(evidence), 'findings': 0},
    'scope_remaining': ['Reconcile localized dates, numbers, time zones and pluralization',
                        'Verify loading and error announcements with assistive technology',
                        'Complete UI09 scope and final release audit'],
})
maintenance.create(out / 'helper-retirement-plan.json', {'containers': retire})
for row in retire:
    current = json.loads(subprocess.check_output(['docker', 'inspect', row['id']], timeout=30))[0]
    assert current['State']['Status'] == 'exited' and current['State']['ExitCode'] == 0
    assert subprocess.check_output(['docker', 'rm', row['id']], text=True, timeout=30).strip() == row['id']
maintenance.create(out / 'helper-retirement.json', {'containers_retired': retire, 'checkpoint_and_diagnostics_retained': True})
maintenance.phase(state, 'preserved_core25_installed_UI09_partial')
print(json.dumps({'result': 'installed_core25_dialog_and_reflow_verified', 'retired_containers': len(retire)}))
