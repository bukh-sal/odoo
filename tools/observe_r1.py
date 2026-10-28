"""Read-only independent adoption/observation of the existing disposable R1 site.

Bootstrap creates local operator-owned target/trust/catalog files, never alters
the application database, image, running workers or existing harness state.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from reference_package import assemble

OPERATOR = ROOT / '.local/operator'


def write_new(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def bootstrap():
    target = OPERATOR / 'targets/r1.json'
    trust = OPERATOR / 'trust.json'
    if target.exists() or trust.exists():
        raise RuntimeError('Operator target/trust already exists; inspect instead of repeating bootstrap')
    harness = json.loads((ROOT / '.local/r1/state.json').read_text())
    fixture = json.loads((ROOT / '.local/r1/fixtures.json').read_text())
    qualified = json.loads((ROOT / 'docs/evidence/G4/20261028t033154z/source-identity.json').read_text())
    artifacts = []
    for name in ('notes', 'notes_labels', 'canvas'):
        manifest, raw, _ = assemble(ROOT, 'plugins/' + name + '/plugin.toml')
        digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
        if digest != qualified['packages'][manifest['plugin']['id']]['digest']:
            raise RuntimeError('Current package differs from qualified G4 identity')
        artifacts.append((manifest, raw, digest))
    config = {'schema_version': 1, 'deployment_id': str(uuid4()), 'project': harness['project'],
        'sites': [{'site_id': fixture['site_id'], 'database': harness['active_db']}],
        'image_id': qualified['image_id'], 'generation': 1, 'policy_version': 1,
        'operator_authorization_generation': 1,
        'release_created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    DockerObserver(config)  # Validate target before registering it.
    write_new(target, config)
    digests = frozenset(item[2] for item in artifacts)
    write_new(trust, {'schema_version': 1, 'mode': 'curated', 'approved_digests': sorted(digests),
        'allow_unsigned_development': False, 'generation': 1})
    catalog = Catalog(OPERATOR / 'catalog', ArtifactValidator(TrustPolicy(approved_digests=digests)))
    incoming = OPERATOR / 'incoming'
    incoming.mkdir(mode=0o700, exist_ok=True)
    for manifest, raw, digest in artifacts:
        path = incoming / (manifest['plugin']['id'] + '-' + manifest['plugin']['version'] + '.mplug')
        with path.open('xb') as stream:
            stream.write(raw)
        catalog.add(path, expected_digest=digest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bootstrap', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'docs/evidence/G5') or output.exists():
        raise ValueError('Fresh G5 evidence directory required')
    output.mkdir(parents=True)
    if args.bootstrap:
        bootstrap()
    config = json.loads((OPERATOR / 'targets/r1.json').read_text())
    trust = json.loads((OPERATOR / 'trust.json').read_text())
    catalog = Catalog(OPERATOR / 'catalog', ArtifactValidator(TrustPolicy(approved_digests=frozenset(trust['approved_digests']), generation=trust['generation'])), readonly=True)
    observer = DockerObserver(config)
    observation = observer.read()
    write_new(output / 'observed-metadata.json', observation)
    document = observer.state(observation, catalog.snapshot())
    write_new(output / 'independent-state.json', document)
    # Repeat metadata observation, not any native initialization or migration.
    repeated = observer.state(observer.read(), catalog.snapshot())
    if data_digest(document) != data_digest(repeated):
        raise RuntimeError('Deployment authority changed during repeated observation; inspect before planning')
    report = {'result': 'passed', 'item': 'E-01b-independent-read', 'utc': datetime.now(timezone.utc).isoformat(),
        'state_digest': data_digest(document['state']), 'release_digest': document['state']['release_digest'],
        'deployment_id': config['deployment_id'], 'image_id': config['image_id'],
        'site_ids': document['state']['site_ids'], 'site_installations': len({item['installation_id'] for item in document['state']['installations']}),
        'workspace_feature_rows': len(document['state']['installations']), 'bindings': len(document['state']['bindings']),
        'python_distributions': len(document['python_metadata']),
        'observation': 'Two matching PostgreSQL REPEATABLE READ READ ONLY metadata snapshots plus static image/source/Python metadata; no native plugin/ORM import.',
        'limitations': ['No executor/apply approval or mutation.', 'Operator-store OS separation not yet qualified.', 'External-service and differing per-workspace provider adapters remain later work.']}
    write_new(output / 'independent-observation.json', report)
    print(json.dumps({key: report[key] for key in ('result', 'item', 'site_installations', 'workspace_feature_rows', 'bindings', 'python_distributions')}))


if __name__ == '__main__':
    main()
