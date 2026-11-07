"""Once-only consolidated release fixtures; all state and diagnostics are private."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'release'), str(ROOT / 'tools'),
               str(ROOT / 'packages/platform_sdk'),
               str(ROOT / 'docs/evidence/post-r1/shared-foundation')]
from initialize_reference import Reference, inspect_image, load, write, configuration
from background_site import BackgroundSite, CATALOG_PLUGINS
from stress_sites import ADDONS, POSTGRES, PROXY, SEED_APP
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_planning import prepare_current_install_targets, installation_id
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from stress_http import StressClient


class FoundationSite(BackgroundSite):
    def __init__(self, args):
        self.args = args
        self.local = ROOT / '.local/foundation-release' / args.run / args.site
        self.private = self.local / 'operator'

    def provision(self):
        for action in ('prepare', 'initialize', 'observe', 'install_notes', 'install_background', 'workflow'):
            getattr(self, action)()

    def prepare(self):
        record = load(self.args.candidate)
        runtime = inspect_image(record['image_id'])
        assert record['state'] == 'built'
        assert runtime['inventory_digest'] == record['inventory_digest']
        assert runtime['inventory']['policy'] == load(ROOT / 'deploy/distribution-r1-foundation.json')
        trust = dict(schema_version=1, mode='curated', generation=1,
                     allow_unsigned_development=False,
                     approved_digests=[record['artifacts'][p]['digest'] for p in CATALOG_PLUGINS])
        subnet = 0 if self.args.site == 'aurora' else 32
        self.prepare_resources(dict(images={k: {'image_id': v} for k, v in {
            'application': record['image_id'], 'postgres': POSTGRES, 'proxy': PROXY}.items()},
            application_inventory_digest=record['inventory_digest']), record['git_base'],
            json.dumps(trust).encode(), subnets={
                'runtime': f'10.203.156.{subnet}/28', 'edge': f'10.203.156.{subnet+16}/28'})
        self.admit(record)

    def initialize(self):
        state = self.state()
        assert state['phase'] == 'configured'
        self.initialize_core(state, 'mp_shell,auth_password_policy,' + ADDONS[self.args.site])
        raw = self.native(state, 'foundation-app-seed', [],
                          'APP = ' + repr(ADDONS[self.args.site]) + '\n' + SEED_APP)
        rows = [json.loads(s.split('=', 1)[1]) for s in raw.decode().splitlines()
                if s.startswith('MP_STRESS_RESULT=')]
        assert len(rows) == 1, 'Inspect seed transaction before another mutation'
        write(self.local / 'app-fixtures.json', rows[0])
        self.publish(state, prepare_assets=False)

    def observe(self):
        target = load(self.private / 'target.json')
        observer = DockerObserver(target)
        observed = observer.read()
        catalog = Catalog(self.private / 'catalog', configuration(self.private / 'trust.json'), readonly=True)
        current = observer.state(observed, catalog.snapshot())
        modules = {r['addon']: r['version'] for r in observed['sites'][0]['native_modules']}
        assert ADDONS[self.args.site] in modules
        assert ADDONS[next(k for k in ADDONS if k != self.args.site)] not in modules
        assert 'mp_example_background' not in modules
        result = dict(result='passed', image=target['image_id'], generation=target['generation'],
                      native_modules=modules, observed_installations=len(current['state']['installations']),
                      common_policy=True, distinct_app_set=True)
        path = self.local / 'baseline-observed.json'
        assert not path.exists()
        write(path, result)
        print(json.dumps(result))

    def install_notes(self):
        self.install_selected(['org.example.notes'], 'notes-install')

    def install_background(self):
        self.install_selected(['org.example.background'], 'background-install')

    def install_selected(self, plugins, label):
        path = self.local / (label + '.json')
        assert not path.exists(), 'Inspect the recorded attempt before mutation'
        target_path = self.private / 'target.json'
        target = load(target_path)
        validator = configuration(self.private / 'trust.json')
        catalog_path = self.private / 'catalog'
        catalog = Catalog(catalog_path, validator, readonly=True)
        executor = NativeExecutor(OperatorStore(self.private / 'control'), target_path, catalog_path, validator)
        observed = executor.observer.read()
        fixture = load(self.local / 'fixtures.json')
        targets = [dict(installation_id=installation_id(observed['sites'][0], plugin),
                        site_id=observed['sites'][0]['site_id'], workspace_id=w['public_id'],
                        plugin_id=plugin, action='install')
                   for w in fixture['workspaces'].values() for plugin in plugins]
        bundle = prepare_current_install_targets(executor.observer.state(observed, catalog.snapshot()),
            observed['sites'], catalog.snapshot(), activation_targets=targets, operation_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        result = dict(phase='registering', operation_id=bundle['plan']['operation_id'], plan_hash=bundle['plan_hash'])
        write(path, result)
        store = executor.store
        store.register(bundle, executor._validate())
        store.review(result['operation_id'], executor._validate())
        store.approve(result['operation_id'], exact_hash=bundle['plan_hash'], noninteractive=True,
                      revalidate=executor._validate(), acknowledgments={'destructive': False, 'trust_expansion': True, 'permission_expansion': True})
        result['phase'] = 'applying'
        write(path, result)
        applied = executor.apply(result['operation_id'])
        assert applied['state'] == 'completed'
        result.update(phase='verified', image=load(target_path)['image_id'])
        write(path, result)
        print(json.dumps(result))

    def resume_notes_install(self):
        # Only the observed pre-mutation acknowledgement refusal is resumable.
        path = self.local / 'notes-install.json'
        result = load(path)
        assert result['phase'] == 'registering'
        executor = NativeExecutor(OperatorStore(self.private / 'control'), self.private / 'target.json',
                                  self.private / 'catalog', configuration(self.private / 'trust.json'))
        status = executor.store.status(result['operation_id'])
        assert status['state'] == 'awaiting_operator_approval' and not status['mutation_started']
        executor.store.approve(result['operation_id'], exact_hash=result['plan_hash'], noninteractive=True,
            revalidate=executor._validate(),
            acknowledgments={'destructive': False, 'trust_expansion': True, 'permission_expansion': True})
        result['phase'] = 'applying'
        write(path, result)
        applied = executor.apply(result['operation_id'])
        assert applied['state'] == 'completed'
        result.update(phase='verified', image=load(self.private / 'target.json')['image_id'])
        write(path, result)
        print(json.dumps(result))

    def workflow(self):
        label = self.args.label
        assert label.replace('-', '').isalnum()
        path = self.local / ('workflow-' + label + '.json')
        assert not path.exists(), 'Use a distinct evidence label'
        alice, bob, operator = [StressClient(self, who) for who in ('alice', 'bob', 'operator')]
        notes = {}
        for space, writer in [('A', alice), ('B', bob)]:
            title = 'Consolidated scoped fixture ' + space
            if label == 'baseline':
                assert writer.native('search_count', [[('title', '=', title)]], workspace=space) == 0
                writer.native('create', [{'title': title, 'body': 'Synthetic migration witness'}], workspace=space)
            rows = alice.native('search_read', [[]], {'fields': ['title', 'revision']}, workspace=space)
            assert len(rows) == 1 and rows[0]['title'] == title
            notes[space] = rows[0]['id']
        alice.native('create', [{'title': 'Denied viewer write'}], workspace='B', deny=True)
        bob.native('read', [[notes['A']], ['title']], workspace='B', deny=True)
        alice.native('read', [[notes['B']], ['title']], workspace='A', deny=True)
        app = load(self.local / 'app-fixtures.json')
        if self.args.site == 'aurora':
            model, ident, reader, denied = 'mp.aurora.task', app['task'], bob, operator
            field, expected = 'stage_id', app['done']
        else:
            model, ident, reader, denied = 'maintenance.request', app['request'], alice, bob
            field, expected = 'stage_id', app['done']
        if label == 'baseline':
            assert reader.native('write', [[ident], {field: expected}], workspace=None, model=model)
        row = reader.native('read', [[ident], ['name', field]], workspace=None, model=model)[0]
        assert row[field][0] == expected
        denied.native('read', [[ident], ['name']], workspace=None, model=model, deny=True)
        views = reader.native('get_views', [], {'views': [[False, 'list'], [False, 'form']]},
                              workspace=None, model=model)
        assert 'list' in views['views'] and 'form' in views['views']
        result = dict(result='passed', label=label, site=self.args.site,
                      image=load(self.private / 'target.json')['image_id'],
                      stock_list_form=True, workflow_preserved=True, app_denial=True,
                      scoped_notes=notes, cross_scope_and_viewer_denied=True)
        write(path, result)
        print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['provision', 'prepare', 'initialize', 'observe', 'status', 'install_notes', 'resume_notes_install', 'install_background', 'workflow'])
    parser.add_argument('site', choices=ADDONS)
    parser.add_argument('--run', default='cf-01')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--label', default='baseline')
    args = parser.parse_args()
    if args.run != 'cf-01':
        parser.error('Only the explicitly owned cf-01 fixture is supported')
    args.port = {'aurora': 18130, 'maintenance': 18131}[args.site]
    getattr(FoundationSite(args), args.phase)()


if __name__ == '__main__':
    main()
