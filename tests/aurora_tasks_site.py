"""Once-only native Tasks qualification with actual image archives and independent approval."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'release'), str(ROOT/'tools'), str(ROOT/'packages/platform_sdk')]
from initialize_reference import Reference, Catalog, DockerObserver, configuration, inspect_image, load, write
from modular_platform.lifecycle_planning import prepare_current_image_install
from modular_platform.operator_store import OperatorStore

POSTGRES = 'sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'
PROXY = 'sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f'


class TasksSite(Reference):
    def __init__(self, args):
        if not re.fullmatch(r'at[0-9]{2}-[a-z0-9-]{1,50}', args.run):
            raise ValueError('Explicit bounded Tasks test run name required')
        self.args = args
        self.local = ROOT/'.local/aurora-tasks'/args.run
        self.private = self.local/'operator'

    def prepare(self):
        record = load(self.args.candidate)
        assert record['state'] == 'built' and record['result'] == 'built_not_deployed'
        runtime = inspect_image(record['image_id'])
        assert runtime['inventory_digest'] == record['inventory_digest']
        assert runtime['inventory']['policy'] == load(ROOT/'deploy/distribution-r1-foundation.json')
        # Inspect all existing addresses before selecting fresh project-owned networks.
        ids = subprocess.run(['docker', 'network', 'ls', '-q'], check=True, capture_output=True).stdout.decode().split()
        existing = json.loads(subprocess.run(['docker', 'network', 'inspect', *ids], check=True, capture_output=True).stdout)
        networks = [ipaddress.ip_network(row['Subnet']) for net in existing for row in (net.get('IPAM', {}).get('Config') or []) if row.get('Subnet')]
        chosen = None
        for offset in range(0, 224, 32):
            pair = [ipaddress.ip_network(f'10.203.159.{offset}/28'), ipaddress.ip_network(f'10.203.159.{offset+16}/28')]
            if not any(a.version == b.version and a.overlaps(b) for a in pair for b in networks):
                chosen = dict(zip(['runtime', 'edge'], map(str, pair))); break
        if chosen is None:
            raise ValueError('No inspected free test subnet pair')
        trust = dict(schema_version=1, mode='curated', generation=1, allow_unsigned_development=False,
                     approved_digests=sorted(row['digest'] for row in record['artifacts'].values()))
        self.prepare_resources(dict(images={k: dict(image_id=v) for k, v in {
            'application': record['image_id'], 'postgres': POSTGRES, 'proxy': PROXY}.items()},
            application_inventory_digest=record['inventory_digest']), record['git_base'],
            json.dumps(trust).encode(), subnets=chosen)
        self.admit()

    def admit(self):
        state = self.state()
        assert state['phase'] == 'configured'
        record = load(self.args.candidate)
        assert (state['image_id'], state['inventory_digest']) == (record['image_id'], record['inventory_digest'])
        trust = configuration(self.private/'trust.json')
        catalog = Catalog(self.private/'catalog', trust)
        for plugin, row in sorted(record['artifacts'].items()):
            assert re.fullmatch(r'[a-z0-9._-]+\.mplug', row['file'])
            archive = self.private/row['file']
            if archive.exists():
                payload = archive.read_bytes()
            else:
                payload = self.command('read-archive-'+plugin.replace('.', '-'), ['docker', 'run', '--rm', '--network', 'none',
                    '--log-driver', 'none', '--entrypoint', '/bin/cat', record['image_id'], '/opt/modular/artifacts/'+row['file']])
                with archive.open('xb') as stream: stream.write(payload)
            assert 'sha256:'+hashlib.sha256(payload).hexdigest() == row['digest']
            if row['digest'] not in {r['digest'] for r in catalog.snapshot()}:
                catalog.add(archive, expected_digest=row['digest'])
        assert {r['digest'] for r in catalog.snapshot()} == set(load(self.private/'trust.json')['approved_digests'])
        self.phase(self.state(), 'archives_admitted')

    def initialize(self):
        state = self.state()
        assert state['phase'] == 'archives_admitted'
        self.phase(state, 'starting_empty_database')
        self.compose(state, 'up', '-d', '--wait', '--no-deps', 'db')
        assert self.sql(state, 'assert-new-database', "SELECT count(*) FROM pg_database WHERE datname='"+state['database']+"';", database='postgres').strip() == b'0'
        self.command('create-empty-database', ['docker', 'exec', state['project']+'-db-1', 'createdb', '-U', 'postgres', '-O', 'modular', '-T', 'template0', state['database']])
        self.native(state, 'core-init', ['-i', 'mp_shell,auth_password_policy', '--stop-after-init', '--without-demo'])
        raw = self.native(state, 'core-provision', [], (ROOT/'tests/aurora_tasks_seed.py').read_text())
        rows = [json.loads(r.split('=', 1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_REFERENCE_RESULT=')]
        assert len(rows) == 1
        assert rows[0]['workspaces'] == {}
        write(self.local/'fixtures.json', rows[0])
        self.publish(state, prepare_assets=False)

    def install(self):
        state = self.state()
        assert state['phase'] == 'core_only_ready'
        target = self.private/'target.json'
        trust = self.private/'trust.json'
        catalog = Catalog(self.private/'catalog', configuration(trust), readonly=True)
        reader = DockerObserver(load(target)); observed = reader.read()
        record = load(self.args.candidate); app = record['artifacts']['dev.aurora.tasks']
        bundle = prepare_current_image_install(reader.state(observed, catalog.snapshot()), observed['sites'],
            catalog.snapshot(), site_id=state['site_id'], workspace_ids=[], site_native=True,
            plugin_id='dev.aurora.tasks', version=app['version'], artifact_digest=app['digest'],
            operation_id=str(uuid4()), created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        write(self.local/'install-bundle.json', bundle)
        cli = [sys.executable, '-I', str(ROOT/'tools/modular.py'), '--config', str(trust)]
        options = ['--deployment-config', str(target), '--catalog', str(self.private/'catalog')]
        store = ['--store', str(self.private/'control')]; operation = bundle['plan']['operation_id']
        self.phase(state, 'registering_native_install')
        self.command('register-native-install', cli+['operations', *store, 'register', '--bundle', str(self.local/'install-bundle.json'), *options])
        self.command('approve-native-install', cli+['operations', *store, 'approve', operation, '--plan-hash', bundle['plan_hash'], '--noninteractive', '--ack-trust', '--ack-permissions', *options])
        self.phase(state, 'applying_native_install')
        result = json.loads(self.command('apply-native-install', cli+['plugin', 'apply', operation, *store, *options], timeout=600))
        assert result['state'] == 'completed'
        self.verify_install()

    def verify_install(self):
        state = self.state()
        assert state['phase'] == 'applying_native_install'
        assert load(self.local/'logs/apply-native-install.stdout')['state'] == 'completed'
        target = self.private/'target.json'
        catalog = Catalog(self.private/'catalog', configuration(self.private/'trust.json'), readonly=True)
        reader = DockerObserver(load(target)); after = reader.state(reader.read(), catalog.snapshot())['state']
        write(self.local/'installed-state.json', after)
        assert len(after['installations']) == 1
        app = after['installations'][0]
        assert app['plugin_id'] == 'dev.aurora.tasks' and app['workspace_id'] is None
        assert self.sql(state, 'verify-no-workspace-authority', 'SELECT (SELECT count(*) FROM mp_workspace),(SELECT count(*) FROM mp_membership),(SELECT count(*) FROM mp_workspace_plugin);').strip() == b'0|0|0'
        self.phase(state, 'native_installed')

    def probe(self):
        state = self.state()
        assert state['phase'] == 'native_installed'
        target = load(self.private/'target.json')
        state.update(database=target['sites'][0]['database'], image_id=target['image_id'])
        source = 'FIXTURE = '+repr(load(self.local/'fixtures.json'))+'\n'+(ROOT/'tests/aurora_tasks_native.py').read_text()
        raw = self.native(state, 'native-probe', [], source)
        rows = [json.loads(r.split('=', 1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_RESULT=')]
        assert len(rows) == 1
        write(self.local/'native-probe.json', rows[0])
        self.phase(state, 'native_probed')

    def edges(self):
        state=self.state()
        assert state['phase']=='native_probed'
        target=load(self.private/'target.json')
        state.update(database=target['sites'][0]['database'],image_id=target['image_id'])
        source='FIXTURE='+repr(load(self.local/'fixtures.json'))+'\n'+(ROOT/'tests/aurora_tasks_edges.py').read_text()
        raw=self.native(state,'native-edges',[],source)
        rows=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_EDGES=')]
        assert len(rows)==1
        write(self.local/'native-edges.json',rows[0])
        self.phase(state,'native_edges_passed')

    def retire(self):
        state=self.state()
        assert not (self.local/'retired.json').exists()
        operation=load(self.local/'install-bundle.json')['plan']['operation_id']
        assert OperatorStore(self.private/'control').status(operation)['state']=='completed'
        if (self.local/'managed-profile.json').exists():
            drain=load(self.local/'managed-drain.json')
            assert drain['state'] in {'drained','paused'}
            assert all(pool['running']==0 for pool in drain.get('pools',{}).values())
        project=state['project']
        assert re.fullmatch(r'mp-r0-r1release[0-9a-f]{12}',project)
        names=subprocess.run(['docker','ps','-a','--format','{{.Names}}'],check=True,capture_output=True).stdout.decode().splitlines()
        selected=[name for name in names if name.startswith(project+'-')]
        if selected:
            inspected=json.loads(self.command('retirement-container-inventory',['docker','inspect',*selected]))
            assert all(row['Name'].lstrip('/') in selected and row['Image'] in {state['image_id'],POSTGRES,PROXY} for row in inspected)
        for kind in ['volumes','networks']:
            for name in state['owned_resources'][kind]:
                singular={'volumes':'volume','networks':'network'}[kind]
                row=json.loads(self.command('retirement-inspect-'+name,['docker',singular,'inspect',name]))[0]
                assert name.startswith(project+'_') and row['Labels']['com.modular.disposable']==project
        self.phase(state,'retiring_owned_site')
        if selected:self.command('retire-containers',['docker','rm','-f',*selected])
        self.command('retire-volumes',['docker','volume','rm',*state['owned_resources']['volumes']])
        self.command('retire-networks',['docker','network','rm',*state['owned_resources']['networks']])
        self.verify_retirement()

    def verify_retirement(self):
        state=self.state();project=state['project']
        assert state['phase']=='retiring_owned_site'
        selected=[r['Name'].lstrip('/') for r in load(self.local/'logs/retirement-container-inventory.stdout')]
        for kind in ['container','volume','network']:
            found=self.command('retirement-verified-'+kind,['docker',kind,'ls',*(['-a'] if kind=='container' else []),'-q','--filter','label=com.modular.disposable='+project])
            assert not found.strip(),kind
        remaining=subprocess.run(['docker','ps','-a','--format','{{.Names}}'],check=True,capture_output=True).stdout.decode().splitlines()
        assert not any(n.startswith(project+'-') for n in remaining)
        write(self.local/'retired.json',dict(result='retired',project=project,containers=selected,
            volumes=state['owned_resources']['volumes'],networks=state['owned_resources']['networks'],
            image_retained_for_comparison=state['image_id'],unrelated_resources_untouched=True))
        self.phase(state,'retired')

    def reconcile_probe(self):
        state=self.state()
        assert state['phase']=='native_edges_passed'
        target=load(self.private/'target.json')
        state.update(database=target['sites'][0]['database'],image_id=target['image_id'])
        source='FIXTURE='+repr(load(self.local/'fixtures.json'))+'\nEXPECT_FIXED=True\n'+(ROOT/'tests/aurora_tasks_reconcile.py').read_text(encoding='utf8')
        raw=self.native(state,'native-reconcile',[],source)
        rows=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_RECONCILE=')]
        assert len(rows)==1 and rows[0]['result']=='passed'
        write(self.local/'native-reconcile.json',rows[0])
        self.phase(state,'native_reconciled')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actions', nargs='+', choices=['prepare', 'admit', 'initialize', 'install', 'verify_install', 'probe', 'edges', 'reconcile_probe', 'retire', 'verify_retirement', 'status'])
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--port', type=int, default=18148)
    args = parser.parse_args()
    site = TasksSite(args)
    for action in args.actions: getattr(site, action)()
