"""Independently provision a disposable site for background qualification."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'release'))
from initialize_reference import (Reference, Catalog, DockerObserver, configuration,
    installation_id, inspect_image, load, prepare_current_install_targets, write)
from reference_package import assemble


PLUGINS = {
    'org.example.notes': 'plugins/notes/plugin.toml',
    'org.example.background': 'plugins/background/plugin.toml',
}
CATALOG_PLUGINS = {**PLUGINS, 'org.example.notes_labels':'plugins/notes_labels/plugin.toml',
                   'org.example.canvas':'plugins/canvas/plugin.toml',
                   'org.example.notes_stats':'plugins/notes_stats/plugin.toml'}


class BackgroundSite(Reference):
    def __init__(self, args):
        self.args = args
        self.local = ROOT / '.local/background-qualification' / args.run
        self.private = self.local / 'operator'

    def prepare(self):
        record = load(self.args.candidate)
        kit = load(ROOT / '.local/releases/stock-r1/images.json')
        images = kit['images']
        runtime = inspect_image(record['image_id'])
        assert runtime['inventory_digest'] == record['inventory_digest']
        assert runtime['inventory']['policy'] == load(ROOT / 'deploy/distribution-r1-background.json')
        trust = dict(schema_version=1, mode='curated', generation=1,
                     allow_unsigned_development=False,
                     approved_digests=[record['artifacts'][plugin]['digest'] for plugin in CATALOG_PLUGINS])
        self.prepare_resources(dict(images={**images, 'application': {'image_id': record['image_id']}},
                                    application_inventory_digest=record['inventory_digest']),
                               record['git_base'], json.dumps(trust).encode(),
                               subnets={
                                   'bg-02-01': {'runtime': '10.203.154.16/28', 'edge': '10.203.154.32/28'},
                                   'bg-03-01': {'runtime': '10.203.154.48/28', 'edge': '10.203.154.64/28'},
                                   'bx-01-history-01': {'runtime': '10.203.154.80/28', 'edge': '10.203.154.96/28'},
                                   'bx-01-retention-01': {'runtime': '10.203.154.112/28', 'edge': '10.203.154.128/28'},
                               }[self.args.run])
        self.admit(record)

    def admit(self, record):
        catalog = Catalog(self.private / 'catalog', configuration(self.private / 'trust.json'))
        for plugin, manifest in CATALOG_PLUGINS.items():
            _, payload, _ = assemble(ROOT, manifest)
            row = record['artifacts'][plugin]
            assert 'sha256:' + hashlib.sha256(payload).hexdigest() == row['digest']
            artifact = self.private / row['file']
            if artifact.exists():
                assert artifact.read_bytes() == payload
            else:
                with artifact.open('xb') as stream:
                    stream.write(payload)
            if row['digest'] not in {item['digest'] for item in catalog.snapshot()}:
                catalog.add(artifact, expected_digest=row['digest'])

    def resume_catalog(self):
        # The first preflight stopped before writing pins or starting an app.
        state = self.state()
        assert state['phase'] == 'publishing_core_bootstrap'
        assert not (self.local / 'logs/bootstrap-release-pins.stdout').exists()
        assert not (self.private / 'target.json').exists()
        record = load(self.args.candidate)
        assert record['image_id'] == state['image_id']
        trust_path = self.private / 'trust.json'
        trust = load(trust_path)
        trust['generation'] += 1
        trust['approved_digests'] = [record['artifacts'][plugin]['digest'] for plugin in CATALOG_PLUGINS]
        write(trust_path, trust)
        self.admit(record)
        self.publish(state, prepare_assets=False)

    def resume_version(self):
        state = self.state()
        assert state['phase'] == 'publishing_core_bootstrap'
        assert not (self.local / 'logs/bootstrap-release-pins.stdout').exists()
        assert not (self.private / 'target.json').exists()
        record = load(self.args.candidate)
        before = inspect_image(state['image_id'])
        after = inspect_image(record['image_id'])
        old, new = before['inventory'], after['inventory']
        assert old['policy'] == new['policy'] and old['artifacts'] == new['artifacts']
        assert before['native_manifests'] == after['native_manifests']
        changed = {name for name in old['files'].keys() | new['files'].keys()
                   if old['files'].get(name) != new['files'].get(name)}
        assert changed == {'packages/platform_sdk/modular_platform/projection.py'}, changed
        assert after['native_manifests']['mp_core']['version'] == '19.0.'+after['platform_version']
        state.update(image_id=record['image_id'],inventory_digest=record['inventory_digest'])
        self.publish(state, prepare_assets=False)

    def initialize(self):
        state = self.state()
        assert state['phase'] == 'configured'
        self.initialize_core(state, 'mp_shell,auth_password_policy')
        self.publish(state, prepare_assets=False)

    def install(self):
        state = self.state()
        assert state['phase'] == 'core_only_ready'
        target = self.private / 'target.json'
        trust = self.private / 'trust.json'
        path = self.private / 'catalog'
        catalog = Catalog(path, configuration(trust), readonly=True).snapshot()
        reader = DockerObserver(load(target))
        observed = reader.read()
        fixtures = load(self.local / 'fixtures.json')
        targets = [dict(installation_id=installation_id(observed['sites'][0], plugin),
                        site_id=state['site_id'], workspace_id=workspace['public_id'],
                        plugin_id=plugin, action='install')
                   for workspace in fixtures['workspaces'].values() for plugin in PLUGINS]
        bundle = prepare_current_install_targets(reader.state(observed, catalog), observed['sites'], catalog,
            activation_targets=targets, operation_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        write(self.local / 'install-bundle.json', bundle)
        cli = [sys.executable, '-I', str(ROOT / 'tools/modular.py'), '--config', str(trust)]
        options = ['--deployment-config', str(target), '--catalog', str(path)]
        store = ['--store', str(self.private / 'control')]
        operation = bundle['plan']['operation_id']
        self.phase(state, 'registering_bg_install')
        self.command('register-bg-install', cli + ['operations', *store, 'register',
            '--bundle', str(self.local / 'install-bundle.json'), *options])
        self.command('approve-bg-install', cli + ['operations', *store, 'approve', operation,
            '--plan-hash', bundle['plan_hash'], '--noninteractive', '--ack-trust', '--ack-permissions', *options])
        self.phase(state, 'applying_bg_install')
        applied = json.loads(self.command('apply-bg-install', cli + ['plugin', 'apply', operation, *store, *options],
                                          timeout=600))
        assert applied['state'] == 'completed'
        self.phase(state, 'background_installed')

    def probe(self):
        state = self.state()
        assert state['phase'] == 'background_installed'
        target = load(self.private / 'target.json')
        state['database'] = target['sites'][0]['database']
        state['image_id'] = target['image_id']
        fixtures = load(self.local / 'fixtures.json')
        source = 'FIXTURE = '+repr(fixtures)+'\n'+(ROOT / 'tests/background_native.py').read_text()
        lines = self.native(state, 'bg02-probe', [], source).decode().splitlines()
        value, = [json.loads(row.split('=',1)[1]) for row in lines if row.startswith('MP_BG_RESULT=')]
        write(self.local / 'bg02-probe.json', value)
        self.phase(state, 'bg02_probed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actions', nargs='+', choices=['prepare', 'initialize', 'resume_catalog', 'resume_version', 'install', 'probe', 'status'])
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--run', choices=['bg-02-01', 'bg-03-01', 'bx-01-history-01', 'bx-01-retention-01'], required=True)
    parser.add_argument('--port', type=int, default=18112)
    args = parser.parse_args()
    for action in args.actions:
        getattr(BackgroundSite(args), action)()
