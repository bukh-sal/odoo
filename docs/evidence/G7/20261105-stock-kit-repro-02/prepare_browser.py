"""Prepare an isolated browser fixture against the exact clean stock kit."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory, verify_private_directory


def load(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('browser', type=Path)
    parser.add_argument('--rtl', action='store_true')
    parser.add_argument('--port', type=int, default=18108)
    args = parser.parse_args()
    site = args.work.resolve() / 'private/reference'
    assert site.parents[2] == ROOT / '.local/stock-webclient-release'
    verify_private_directory(site)
    target = load(site / 'operator/target.json')
    state = load(site / 'state.json')
    image = load(args.kit / 'images.json')['images']['application']['image_id']
    assert target['image_id'] == image and target['project'] == state['project']
    assert target['sites'][0]['database'] == state['database']
    assert state['phase'] == 'kit_backend_worker_reference_qualified' and state['port'] == args.port
    out = args.browser.resolve()
    assert out.parent == ROOT / '.local' and out.name.startswith('sw-browser-') and not out.exists()
    fixture = load(site / 'fixtures.json')
    action = int(subprocess.check_output(['docker', 'exec', state['project'] + '-db-1', 'psql',
        '-XqAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', state['database'], '-c',
        "SELECT res_id FROM ir_model_data WHERE module='mp_example_notes' AND name='action_notes';"], timeout=30))
    if args.rtl:
        script = '''
lang = env["res.lang"]._activate_and_install_lang("ar_001")
assert lang.active and lang.direction == "rtl"
alice = env["res.users"].search([("login", "=", "r1_alice")])
assert len(alice) == 1 and alice.lang == "en_US"
alice.lang = lang.code
env.registry.clear_cache("default", "stable")
env.cr.commit()
env.registry.signal_changes()
'''
        locale = subprocess.run(['docker', 'exec', '-i', target['worker_id'], '/venv/bin/python', 'odoo-bin', 'shell',
            '-c', '/run/secrets/odoo_config', '-d', state['database'], '--no-http', '--workers=0', '--max-cron-threads=0'],
            input=script.encode(), capture_output=True, timeout=90)
        for stream in ('stdout', 'stderr'):
            with (site / 'logs' / ('stock-arabic-activation.' + stream)).open('xb') as handle:
                handle.write(getattr(locale, stream))
        locale.check_returncode()
    protect_directory(out)
    protect_directory(out / 'p')
    workspace = fixture['workspaces']['A']['public_id']
    data = dict(base=state['url'], database=state['database'], fixture=fixture, actor='alice', rtl=args.rtl,
                password_file=str(site / 'account-passwords.json'), image_id=image, profile=str(out / 'p'),
                notes_route=f'/odoo/action-{action}?workspace={workspace}')
    (out / 'browser-input.json').write_text(json.dumps(data), encoding='utf-8')
    (out / 'tables-before.json').write_text('{}', encoding='utf-8')


if __name__ == '__main__':
    main()
