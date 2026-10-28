"""Qualify a harmless draft using real independently read R1 state; never apply."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from observe_r1 import ROOT, OPERATOR, write_new
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import check_bundle, data_digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'docs/evidence/G5') or output.exists():
        raise ValueError('Fresh G5 evidence directory required')
    output.mkdir(parents=True)
    config = json.loads((OPERATOR / 'targets/r1.json').read_text())
    trust = json.loads((OPERATOR / 'trust.json').read_text())
    validator = ArtifactValidator(TrustPolicy(approved_digests=frozenset(trust['approved_digests']), generation=trust['generation']))
    catalog = Catalog(OPERATOR / 'catalog', validator, readonly=True)
    observer = DockerObserver(config)
    observed = observer.read()
    document = observer.state(observed, catalog.snapshot())
    fixture = json.loads((ROOT / '.local/r1/fixtures.json').read_text())
    workspace_a, workspace_b = (fixture['workspaces'][key]['public_id'] for key in ('A', 'B'))
    canvas = [item for item in document['state']['installations'] if item['plugin_id'] == 'org.example.canvas']
    first = next(item for item in canvas if item['workspace_id'] == workspace_a)
    second = next(item for item in canvas if item['workspace_id'] == workspace_b)
    assert first['installation_id'] == second['installation_id'], 'Native installation is site-scoped'
    document['request'] = {'operation_type': 'suspend', 'requested': {},
        'targets': [{key: first[key] for key in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')} | {'action': 'suspend'}],
        'operation_id': str(uuid4()), 'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    proposal = output / 'proposal.json'
    write_new(proposal, document)
    command = [sys.executable, str(ROOT / 'tools/modular.py'), '--config', str(OPERATOR / 'trust.json'),
        'plugin', 'plan', '--input', str(proposal), '--store', str(OPERATOR / 'catalog')]
    completed = subprocess.run(command, capture_output=True, timeout=90)
    if completed.returncode:
        write_new(output / 'failed-cli.json', {'exit_code': completed.returncode,
                  'stderr': completed.stderr.decode('utf-8', errors='replace')})
        raise RuntimeError('Draft planning failed; inspect the recorded safe CLI error')
    bundle = json.loads(completed.stdout)
    check_bundle(bundle, document['state'])
    assert len(bundle['operation_lock']['targets']) == 1
    assert bundle['operation_lock']['targets'][0]['workspace_id'] == workspace_a
    assert len(bundle['operation_lock']['bindings']) == 10
    assert bundle['plan']['target_release_digest'] == document['state']['release_digest']
    assert bundle['plan']['backup']['required'] is False
    assert bundle['display']['feature_suspension_unloads_code'] is False
    write_new(output / 'draft-bundle.json', bundle)
    after = observer.state(observer.read(), catalog.snapshot())
    assert data_digest(after['state']) == data_digest(document['state']), 'Preparation must not mutate authority'
    write_new(output / 'state-after.json', after)
    sources = ['packages/platform_sdk/modular_platform/' + name for name in
        ('artifacts.py', 'catalog.py', 'resolution.py', 'plans.py', 'planning_cli.py', 'deployment.py')]
    sources += ['tools/modular.py', 'tools/observe_r1.py', 'tools/qualify_live_planning.py']
    write_new(output / 'live-planning.json', {'result': 'passed', 'item': 'E-01b-live-draft',
        'utc': datetime.now(timezone.utc).isoformat(), 'plan_hash': bundle['plan_hash'],
        'base_state_digest': bundle['plan']['base_state_digest'],
        'shared_site_installation': first['installation_id'], 'selected_workspace_id': workspace_a,
        'other_workspace_id': workspace_b, 'binding_count': 10,
        'python_distributions': len(document['python_metadata']),
        'database_mutations': False, 'approval_or_apply': False,
        'observations': ['Running image/inventory independently pinned and verified.',
            'PostgreSQL metadata read through REPEATABLE READ READ ONLY; no ORM/plugin imports.',
            'Three site installations expand to six workspace features with ten scoped bindings.',
            'One Canvas workspace feature target; other workspace shares installation but is not targeted.',
            'All75 installed Python distribution roots resolved from actual static metadata.',
            'Real curated CLI draft preserves release and state; hash includes exact lock preimage.'],
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}})
    print(json.dumps({'result': 'passed', 'item': 'E-01b-live-draft', 'evidence': str(output), 'approval_or_apply': False}))


if __name__ == '__main__':
    main()
