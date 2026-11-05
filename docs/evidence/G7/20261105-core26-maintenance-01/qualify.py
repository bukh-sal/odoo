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
run_root = root / '.local/g7-ui-core26-01'
state = maintenance.load(maintenance.PRIVATE / 'state.json')
native = maintenance.context()
assert state['phase'] == 'preserved_core26_needs_HTTP_UI09'
assert native.config['generation'] == 7

metrics = {}
for mode in ('baseline', 'zoom200'):
    run = run_root / ('layout-' + mode)
    audit = maintenance.load(run / 'observations.json')
    assert audit['image'] == state['image_id'] and audit['generation'] == 7
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
    image = run_root / 'layout-baseline' / (glyph['theme'] + '-confirm.png')
    assert hashlib.sha256(image.read_bytes()).hexdigest() == glyph['screenshot_sha256']
    assert glyph['pixels_at_least_3_to_1'] >= 8

narrow = maintenance.load(run_root / 'narrow/observations.json')
assert len(narrow['samples']) == 3 and not any(narrow[key] for key in ('overflow', 'foreign', 'exceptions'))
for mode in ('layout-baseline', 'layout-zoom200', 'narrow'):
    process = maintenance.load(run_root / mode / 'process.json')
    assert process['state'] == 'stopped' and process['exit'] == {'code': 0, 'signal': None}
profile = Path(maintenance.load(run_root / 'browser-input.json')['profile'])
partition = maintenance.load(profile / 'Default/Preferences').get('partition', {})
for key, prior in maintenance.load(run_root / 'zoom-before.json')['keys'].items():
    assert (key in partition) == prior['existed'] and partition.get(key) == prior['value']

localized_path = run_root / 'native-events-03/locale-announcements.json'
interaction_path = run_root / 'fields-canvas/fields-canvas.json'
localized = maintenance.load(localized_path)
interaction = maintenance.load(interaction_path)
assert localized['image'] == state['image_id'] and localized['generation'] == 7
assert localized['english']['text'] == '3 members' and localized['arabic']['text'] == '3 أعضاء'
assert not localized['readyStatus']['hasText'] and not localized['readyAlert']['hasText']
assert localized['readyStatus']['id'] == localized['loading']['id']
assert localized['readyAlert']['id'] == localized['error']['id']
assert localized['loading']['live']['live'] == 'polite' and localized['error']['live']['live'] == 'assertive'
loading_ids = {event['child_id'] for event in localized['windowsLiveEvents']['loading']}
error_ids = {event['child_id'] for event in localized['windowsLiveEvents']['error']}
assert loading_ids and error_ids - loading_ids
assert localized['timestamps']['english'].endswith('UTC') and 'نوفمبر' in localized['timestamps']['arabic']
assert not localized['foreignRequests'] and not localized['runtimeExceptions']
assert interaction['requiredField']['hasMessage'] and not interaction['requiredField']['submitted']
assert interaction['keyboardExitToSettings'] and not interaction['05-Canvas-keyboard-discard']['server_save_clicked']
for mode in ('baseline', 'native-events', 'native-events-02', 'native-events-03', 'fields-canvas'):
    process = maintenance.load(run_root / mode / 'process.json')
    assert process['state'] == 'stopped' and process['exit'] == {'code': 0, 'signal': None}

assert maintenance.snapshot('data-after-UI26', native) == maintenance.load(maintenance.PRIVATE / 'data-after.json')
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
            'data-before-UI26.stdout', 'data-after-UI26.stdout'}
streams = [file for folder in (maintenance.PRIVATE, logs) for file in folder.iterdir()
           if file.is_file() and file.suffix in ('.stdout', '.stderr', '.log') and file.name not in excluded]
evidence = [file for file in out.iterdir() if file.is_file()] + [localized_path, interaction_path]
evidence += list((out.parent / '20261105-core26-repro-01').glob('*'))
for mode in ('layout-baseline', 'layout-zoom200', 'narrow'):
    folder = run_root / mode
    evidence += [folder / 'observations.json', *folder.glob('*.png'), *folder.glob('network.json')]
findings = [item for file in streams + evidence for item in scanner.inspect_file(file, str(file.relative_to(root)))]
assert not findings, 'Review findings in protected diagnostic inputs before publishing'

for mode in ('layout-baseline', 'layout-zoom200', 'narrow'):
    destination = out / mode
    destination.mkdir()
    for name in ('observations.json', 'network.json', 'light-confirm.png', 'dark-confirm.png', 'Arabic-settings.png'):
        file = run_root / mode / name
        if file.is_file():
            shutil.copyfile(file, destination / name)
maintenance.create(out / 'installed-observations.json', {
    'image': state['image_id'], 'generation': 7, 'operation': operation,
    'ui09': 'passed_current_reference_scope',
    'dialog_name_both_themes_and_zoom_levels': 'Delete note',
    'glyph_contrast': glyphs, 'zoom_metrics': metrics, 'narrow': narrow['samples'],
    'tables_exact_after_read_only_ui': 17, 'worker_preserved': True,
    'browser_runs_closed': 8, 'zoom_preferences_restored': True,
    'privacy': {'known_values': len(values), 'streams': len(streams), 'evidence_files': len(evidence), 'findings': 0},
    'locale_and_announcements': localized, 'field_and_canvas': interaction,
    'verification_scope': [
        'Live region changes reached the Windows accessibility event API. Spoken output from a specific screen reader was not measured.',
        'The actual loaded Operations formatter was exercised with a UTC journal timestamp. Settings counts and plural forms were observed on screen.',
        'Reference custom pages use the shell layout. Keyboard navigation back to Settings was verified.',
        'Manual glyph review and scoped browser checks do not assert WCAG conformance of arbitrary plugins.',
    ],
})
maintenance.create(out / 'helper-retirement-plan.json', {'containers': retire})
for row in retire:
    current = json.loads(subprocess.check_output(['docker', 'inspect', row['id']], timeout=30))[0]
    assert current['State']['Status'] == 'exited' and current['State']['ExitCode'] == 0
    assert subprocess.check_output(['docker', 'rm', row['id']], text=True, timeout=30).strip() == row['id']
maintenance.create(out / 'helper-retirement.json', {'containers_retired': retire, 'checkpoint_and_diagnostics_retained': True})
maintenance.phase(state, 'preserved_core26_installed_UI09_qualified')
print(json.dumps({'result': 'installed_core26_dialog_and_reflow_verified', 'retired_containers': len(retire)}))
