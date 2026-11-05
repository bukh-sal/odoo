"""Exercise the upstream Maintenance import boundary on the pinned R1 image."""
import argparse
import ast
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[4]
BASE_TAG = 'modular-platform:stage-20261105t180615917518z'
BASE_ID = 'sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415'
UPSTREAM = '5c7defb49e020fec8b6bb82403a2f54eb79e92e1'
POSTGRES = 'sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'
WORKFLOW = """
import json
from odoo.exceptions import AccessError
from odoo.fields import Command

internal = env.ref('base.group_user')
equipment_manager = env.ref('maintenance.group_equipment_manager')
users = env['res.users']
manager = users.create({'name': 'Probe Manager', 'login': 'probe-manager',
                        'group_ids': [Command.set([internal.id, equipment_manager.id])]})
outsider = users.create({'name': 'Probe Outsider', 'login': 'probe-outsider',
                         'group_ids': [Command.set([internal.id])]})
equipment = env['maintenance.equipment'].with_user(manager).create({'name': 'Probe pump'})
requests = env['maintenance.request']
request = requests.with_user(manager).create({'name': 'Inspect probe pump',
    'equipment_id': equipment.id, 'owner_user_id': manager.id, 'user_id': manager.id})
stage = env['maintenance.stage'].search([('done', '=', True)], limit=1)
assert stage and request.stage_id != stage
request.write({'stage_id': stage.id})
assert request.stage_id == stage and request.equipment_id == equipment
assert not requests.with_user(outsider).search([('id', '=', request.id)])
try:
    requests.with_user(outsider).browse(request.id).read(['name'])
except AccessError:
    pass
else:
    raise AssertionError('A non-participant could read the maintenance request')
assert requests.with_user(manager).get_views([(False, 'list'), (False, 'form')])['views'].keys() >= {'list', 'form'}
modules = env['ir.module.module'].search([('name', 'in', ['html_editor', 'iap', 'mail', 'maintenance'])])
assert set(modules.mapped('state')) == {'installed'} and len(modules) == 4
print('MP_MAINTENANCE_RESULT ' + json.dumps({'installed': sorted(modules.mapped('name')),
    'equipment_created': True, 'request_advanced': True, 'native_list_form': True,
    'outsider_search_and_direct_read_denied': True}))
"""


def command(*args, check=True, input=None, env=None):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf8',
                          errors='replace', timeout=180, check=check, input=input, env=env)


def manifest_closure(installed, root):
    pending = [root]
    added = {}
    while pending:
        name = pending.pop()
        if name in installed or name in added:
            continue
        path = f'addons/{name}/__manifest__.py'
        manifest = ast.literal_eval(command('git', 'show', f'{UPSTREAM}:{path}').stdout)
        if not manifest.get('installable', True):
            raise ValueError(f'{name} is not installable')
        added[name] = manifest
        pending.extend(manifest.get('depends') or ['base'])
    return added


def registry_probe(image, suffix):
    db_name = 'mp_maintenance_probe'
    db_user = 'mp_probe_db'
    db_container = 'mp-maintenance-db-' + suffix
    password = secrets.token_urlsafe(24)
    environment = {**os.environ, 'POSTGRES_PASSWORD': password, 'PGPASSWORD': password}
    db_id = command('docker', 'run', '-d', '--rm', '--pull', 'never', '--network', 'none',
                    '--name', db_container, '--tmpfs', '/var/lib/postgresql/data',
                    '--env', 'POSTGRES_PASSWORD', '--env', 'POSTGRES_DB=' + db_name,
                    '--env', 'POSTGRES_USER=' + db_user,
                    POSTGRES, env=environment).stdout.strip()
    try:
        for _ in range(60):
            ready = command('docker', 'exec', db_id, 'pg_isready', '-h', '127.0.0.1',
                            '-d', db_name, '-U', db_user, check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('The isolated PostgreSQL container did not become ready')
        run = ['-i', '--rm', '--pull', 'never', '--network', 'container:' + db_id,
               '--read-only', '--tmpfs', '/tmp', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--env', 'PGPASSWORD', '--entrypoint', '/venv/bin/python', image, '-B', '/opt/modular/odoo-bin']
        config = ['--db_host=127.0.0.1', '--db_user=' + db_user, '-d', db_name, '--no-http', '--max-cron-threads=0',
                  '--data-dir=/tmp/odoo', '--addons-path=/opt/modular/addons,/probe/declared,/probe/implicit']
        install = command('docker', 'run', '--name', 'mp-maintenance-install-' + suffix,
                          *run, *config, '-i', 'maintenance', '--without-demo=True',
                          '--stop-after-init', env=environment, check=False)
        if install.returncode:
            return {'installed': False, 'error': install.stderr[-4500:]}
        workflow = command('docker', 'run', '--name', 'mp-maintenance-workflow-' + suffix,
                           *run, 'shell', *config, input=WORKFLOW, env=environment, check=False)
        result = next((line for line in workflow.stdout.splitlines() if line.startswith('MP_MAINTENANCE_RESULT ')), None)
        if workflow.returncode or not result:
            return {'installed': True, 'workflow_passed': False, 'error': workflow.stderr[-4500:]}
        return {'workflow_passed': True, **json.loads(result.split(' ', 1)[1])}
    finally:
        assert command('docker', 'inspect', db_id, '--format', '{{.Name}}').stdout.strip() == '/' + db_container
        command('docker', 'rm', '-f', db_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--registry', action='store_true', help='Also exercise native install and ORM on an ephemeral database')
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError(args.receipt)
    policy = json.loads((ROOT / 'deploy/distribution-r1-notes-stats.json').read_bytes())
    assert policy['upstream_commit'] == UPSTREAM
    added = manifest_closure(set(policy['addons']), 'maintenance')
    assert set(added) == {'html_editor', 'mail', 'maintenance'}
    assert command('docker', 'image', 'inspect', BASE_TAG, '--format', '{{.Id}}').stdout.strip() == BASE_ID
    suffix = uuid.uuid4().hex[:12]
    tag = 'mp-disposable-maintenance-import:' + suffix
    with tempfile.TemporaryDirectory(prefix='mp-maintenance-import-') as directory:
        context = Path(directory)
        archive = context / 'addons.zip'
        command('git', 'archive', '--format=zip', '--output', str(archive), UPSTREAM,
                *[f'addons/{name}' for name in sorted({*added, 'iap'})])
        with zipfile.ZipFile(archive) as source:
            source.extractall(context)
        archive.unlink()
        (context / 'implicit').mkdir()
        shutil.move(context / 'addons/iap', context / 'implicit/iap')
        (context / 'Dockerfile').write_text(
            f'FROM {BASE_TAG}\nCOPY addons /probe/declared\nCOPY implicit /probe/implicit\n',
            encoding='utf8',
        )
        build = command('docker', 'build', '--network', 'none', '--tag', tag, str(context), check=False)
        if build.returncode:
            raise RuntimeError(build.stderr[-5000:])
    image = command('docker', 'image', 'inspect', tag, '--format', '{{.Id}}').stdout.strip()
    try:
        run = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
               '--tmpfs', '/tmp', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--entrypoint', '/venv/bin/python', image, '-B', '-c']
        preamble = ("import odoo.addons; odoo.addons.__path__.append('/opt/modular/addons'); "
                    "odoo.addons.__path__.append('/probe/declared'); ")
        declared = command(*run[:2], '--name', 'mp-maintenance-declared-' + suffix, *run[2:],
                           preamble + "import odoo.addons.html_editor", check=False)
        assert declared.returncode != 0 and "No module named 'odoo.addons.iap'" in declared.stderr, declared.stderr
        corrected = command(*run[:2], '--name', 'mp-maintenance-with-iap-' + suffix, *run[2:],
                            preamble + "odoo.addons.__path__.append('/probe/implicit'); "
                            "import odoo.addons.html_editor, odoo.addons.mail, odoo.addons.maintenance",
                            check=False)
        report = {
            'result': 'passed_offline_import_with_explicit_iap' if corrected.returncode == 0 else 'additional_import_failure',
            'upstream_commit': UPSTREAM,
            'base_image': BASE_ID,
            'probe_image': image,
            'declared_additions': sorted(added),
            'declared_external_dependencies': {name: item['external_dependencies'] for name, item in added.items()
                                               if item.get('external_dependencies')},
            'undeclared_import': 'odoo.addons.iap',
            'declared_only_exit': declared.returncode,
            'with_iap_exit': corrected.returncode,
            'with_iap_error': corrected.stderr[-3000:] if corrected.returncode else None,
            'scope': 'Python addon imports in a network-disabled container. Database installation and hosted integration behavior require separate checks.',
        }
        if args.registry and corrected.returncode == 0:
            report['registry'] = registry_probe(image, suffix)
    finally:
        assert command('docker', 'image', 'inspect', tag, '--format', '{{.Id}}').stdout.strip() == image
        command('docker', 'image', 'rm', tag)
    report['probe_tag_removed'] = True
    with args.receipt.open('x', encoding='utf8') as receipt:
        json.dump(report, receipt, indent=2)
        receipt.write('\n')
    print(json.dumps(report))
    return corrected.returncode or int(args.registry and not report['registry'].get('workflow_passed'))


if __name__ == '__main__':
    raise SystemExit(main())
