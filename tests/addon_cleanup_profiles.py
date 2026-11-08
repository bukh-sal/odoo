"""Once-only clean extraction profiles; private owned state and no resets."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

from foundation_release import (FoundationSite, ROOT, inspect_image, load, write,
                                POSTGRES, PROXY, CATALOG_PLUGINS)

PROFILES = {'core': ('', 18141, 32), 'maintenance': ('maintenance', 18142, 64),
            'communication': ('mp_discuss,mp_mail_gateway', 18143, 96),
            'aurora': ('mp_aurora_tasks', 18161, 128), 'regression': ('mp_mail_gateway', 18160, 160),
            'layout-regression': ('test_foundation_flow', 18162, 192)}


class CleanupProfile(FoundationSite):
    def __init__(self, args):
        self.args = args
        self.local = ROOT / '.local/addon-cleanup/profiles' / args.run / args.profile
        self.private = self.local / 'operator'

    def prepare(self):
        record = load(self.args.candidate)
        runtime = inspect_image(record['image_id'])
        assert record['state'] == 'built' and runtime['inventory_digest'] == record['inventory_digest']
        assert runtime['inventory']['policy'] == load(ROOT / 'deploy/distribution-r1-foundation.json')
        trust = dict(schema_version=1, mode='curated', generation=1,
                     allow_unsigned_development=False,
                     approved_digests=[record['artifacts'][p]['digest'] for p in CATALOG_PLUGINS])
        subnet = PROFILES[self.args.profile][2]
        self.prepare_resources(dict(images={k: {'image_id': v} for k, v in {
            'application': record['image_id'], 'postgres': POSTGRES, 'proxy': PROXY}.items()},
            application_inventory_digest=record['inventory_digest']), record['git_base'],
            json.dumps(trust).encode(), subnets={
                'runtime': f'10.203.157.{subnet}/28', 'edge': f'10.203.157.{subnet+16}/28'})
        self.admit(record)

    def initialize(self):
        state = self.state()
        assert state['phase'] == 'configured'
        extra = PROFILES[self.args.profile][0]
        if self.args.profile in ('regression', 'layout-regression'):
            # A separate clean native regression DB uses its default test users;
            # it is never published as an application or mixed with operator data.
            self.phase(state, 'starting_regression_database')
            self.compose(state, 'up', '-d', '--wait', '--no-deps', 'db')
            assert self.sql(state, 'assert-new-regression-database',
                "SELECT count(*) FROM pg_database WHERE datname='" + state['database'] + "';",
                database='postgres').strip() == b'0'
            self.command('create-regression-database', ['docker', 'exec', state['project'] + '-db-1',
                'createdb', '-U', 'postgres', '-O', 'modular', '-T', 'template0', state['database']])
            if self.args.profile == 'layout-regression':
                self.layout_regressions(state)
            else:
                self.native(state, 'ar-native-regressions', ['-i', 'html_editor,mp_mail_gateway',
                    '--stop-after-init', '--without-demo', '--test-enable', '--test-tags',
                    '/mp_mail_gateway,/html_editor:TestController'])
            # Native runner's zero exit is required. Inspect the summary/log for
            # actual executed count and failures before issuing any gate decision.
            self.phase(state, 'native_regression_process_completed')
            return
        self.initialize_core(state, 'mp_shell,auth_password_policy' + (',' + extra if extra else ''))
        self.publish(state)

    def layout_regressions(self, state):
        source=(ROOT/'tests/addons/test_foundation_flow').resolve()
        assert source.is_relative_to(ROOT/'tests') and (source/'__manifest__.py').is_file()
        # Docker Desktop blocked both a broad Windows bind and a minimal one
        # before container creation. Stream only the reviewed fixture into one
        # tracked owned volume, then mount it read-only for the native runner.
        volume=state['project']+'_testaddons'
        assert volume not in state['owned_resources']['volumes']
        state['owned_resources']['volumes'].append(volume)
        self.phase(state,'staging_native_regression_source')
        self.command('create-testaddons-volume',['docker','volume','create','--label',
            'com.modular.disposable='+state['project'],'--label',
            'com.docker.compose.project='+state['project'],volume])
        stream=io.BytesIO();hashes={}
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for relative in ('__init__.py','__manifest__.py','tests/__init__.py','tests/test_flow.py'):
                path=source/relative;assert path.is_file() and not path.is_symlink()
                raw=path.read_bytes();hashes[relative]=hashlib.sha256(raw).hexdigest()
                info=tarfile.TarInfo('test_foundation_flow/'+relative)
                info.size=len(raw);info.mode=0o444
                archive.addfile(info,io.BytesIO(raw))
        write(self.local/'native-fixture-source.json',dict(image_id=state['image_id'],sha256=hashes,
            tar_sha256=hashlib.sha256(stream.getvalue()).hexdigest(),readonly_runner=True))
        self.command('stream-native-regression-source',['docker','run','--rm','-i','--log-driver','none',
            '--name',state['project']+'-fixture-stage','--label','com.modular.disposable='+state['project'],
            '--network','none','--read-only','--user','0:0','--cap-drop','ALL',
            '--mount','type=volume,source='+volume+',target=/fixture',
            '--entrypoint','/venv/bin/python',state['image_id'],'-c',
            "import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|*').extractall('/fixture',filter='data')"],data=stream.getvalue(),timeout=90)
        label='ar-owned-foundation-tests'
        self.phase(state,label)
        self.command(label,['docker','run','--name',state['project']+'-'+label,
            '--label','com.modular.disposable='+state['project'],'--log-driver','none',
            '--network',state['project']+'_runtime','--read-only','--user','10001:10001',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp',
            '--memory','1536m','--pids-limit','128','--mount',
            'type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly',
            '--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular',
            '--mount','type=volume,source='+volume+',target=/run/ar-tests,readonly',
            '--entrypoint','/venv/bin/python',state['image_id'],'odoo-bin',
            '-c','/run/secrets/odoo_config','-d',state['database'],'--no-http',
            '--workers=0','--max-cron-threads=0','--stop-after-init','--without-demo',
            '--addons-path=/opt/modular/addons,/run/ar-tests','-i','test_foundation_flow',
            '--test-enable','--test-tags','/test_foundation_flow'],timeout=300)

    def verify(self):
        code = '''
import json
from unittest.mock import patch
installed = {m.name: m.installed_version for m in env['ir.module.module'].search([('state', '=', 'installed')])}
assert 'iap' not in installed
assert not env['ir.module.module'].search_count([('to_buy', '=', True)])
assert not env['ir.actions.act_url'].search_count([('url', 'like', 'apps.odoo.com')])
assert not {'module_sms','module_auth_ldap','module_auth_oauth','module_web_unsplash','module_partner_autocomplete'} & env['res.config.settings']._fields.keys()
from odoo.addons.html_editor.controllers import main
assert not hasattr(main, 'iap_tools')
assert main.link_preview.__name__ == 'odoo.addons.html_editor.tools.link_preview'
assert not any(hasattr(main.HTML_Editor, name) for name in ('generate_text','save_library_media','media_library_search'))
if PROFILE == 'core':
    assert not {'mail','maintenance','mp_aurora_tasks','mp_discuss','mp_mail_gateway','web_tour'} & installed.keys()
    assert 'mail.ice.server' not in env and 'fetchmail.server' not in env
    from types import SimpleNamespace
    with patch.object(main, 'request', SimpleNamespace(env=env)):
        assert main.HTML_Editor().get_ice_servers() == []
elif PROFILE == 'maintenance':
    assert 'mail' in installed and 'maintenance' in installed
    assert not {'mp_discuss','mp_mail_gateway','web_tour'} & installed.keys()
    assert 'fetchmail.server' not in env
    assert not env.ref('mp_discuss.action_discuss', raise_if_not_found=False)
    with patch('requests.sessions.Session.request', side_effect=AssertionError('No external requests')):
        request = env['maintenance.request'].create({'name': 'AR native record', 'description': '<p>Local editor witness</p>'})
        message = request.message_post(body='<p>Native chatter witness</p>', message_type='comment')
        assert message.res_id == request.id
        views = request.get_views([(False, 'list'), (False, 'form')])
        assert {'list','form'} <= views['views'].keys()
elif PROFILE == 'communication':
    assert {'mail','mp_discuss','mp_mail_gateway','web_tour'} <= installed.keys()
    assert 'fetchmail.server' in env
    assert env.ref('mp_discuss.action_discuss').tag == 'mail.action_discuss'
    assert env.ref('mp_mail_gateway.ir_cron_mail_gateway_action')
    assert not env.ref('mail.action_discuss', raise_if_not_found=False)
elif PROFILE == 'aurora':
    assert 'mp_aurora_tasks' in installed and 'mail' not in installed
print('MP_AR_PROFILE=' + json.dumps(dict(result='passed', profile=PROFILE, installed=installed,
    no_iap=True, no_vendor_catalog=True, optional_app_boundary=True)))
'''
        raw = self.native(self.state(), 'ar-profile-verify', [], 'PROFILE=' + repr(self.args.profile) + '\n' + code)
        rows = [json.loads(line.split('=', 1)[1]) for line in raw.decode().splitlines()
                if line.startswith('MP_AR_PROFILE=')]
        assert len(rows) == 1, 'Inspect diagnostics/transaction before another mutation'
        write(self.local / 'verified.json', rows[0])
        print(json.dumps(rows[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'initialize', 'verify', 'status'])
    parser.add_argument('profile', choices=PROFILES)
    parser.add_argument('--run', required=True)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    args.port = PROFILES[args.profile][1]
    getattr(CleanupProfile(args), args.phase)()


if __name__ == '__main__':
    main()
