"""Once-only consolidated release fixtures; all state and diagnostics are private."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'release'), str(ROOT / 'tools'),
               str(ROOT / 'packages/platform_sdk'),
               str(ROOT / 'docs/evidence/post-r1/shared-foundation')]
from initialize_reference import Reference, inspect_image, load, write, configuration
from background_site import BackgroundSite, CATALOG_PLUGINS
from stress_sites import ADDONS, POSTGRES, PROXY, SEED_APP
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver


class FoundationSite(BackgroundSite):
    def __init__(self, args):
        self.args = args
        self.local = ROOT / '.local/foundation-release' / args.run / args.site
        self.private = self.local / 'operator'

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'initialize', 'observe', 'status'])
    parser.add_argument('site', choices=ADDONS)
    parser.add_argument('--run', default='cf-01')
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    if args.run != 'cf-01':
        parser.error('Only the explicitly owned cf-01 fixture is supported')
    args.port = {'aurora': 18130, 'maintenance': 18131}[args.site]
    getattr(FoundationSite(args), args.phase)()


if __name__ == '__main__':
    main()
