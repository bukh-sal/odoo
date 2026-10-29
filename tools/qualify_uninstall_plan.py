"""Prepare/reconstruct uninstall proposals read-only; never request/approve/apply."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.approval_validation import IndependentValidator
from modular_platform.catalog import Catalog
from modular_platform.contracts import plan_hash
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_impact import impact_view
from modular_platform.plans import _display, check_bundle, data_digest
from modular_platform.uninstall_planning import prepare_current_image_uninstall
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'docs/evidence/G5') or output.exists():
        raise ValueError('Fresh owned G5 evidence directory required')
    local = ROOT / '.local/g5-lifecycle'
    target = local / 'operator/target.json'
    config = json.loads(target.read_text(encoding='utf8'))
    state = json.loads((local / 'state.json').read_text(encoding='utf8'))
    assert state['disposable'] and config['project'] == state['project'] == 'mp-r0-r1lifef99acae9d906'
    assert config['generation'] == 3 and config['sites'][0]['database'] == state['active_db'] == 'mp_disposable_r0_r1_g5_life_f99acae9d906'
    assert config['image_id'] == 'sha256:154d74a9d63337cb64607affb78104462a5eb9ab97afe8cd9a5ede48b65b8c5a'
    protected = [ROOT / '.local/operator/targets/g5.json', ROOT / '.local/g5-manager-upgrade/operator/target.json', target]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    validator = configuration(ROOT / '.local/operator/trust.json')
    catalog_root = ROOT / '.local/operator/catalog'
    catalog = Catalog(catalog_root, validator, readonly=True)
    observer = DockerObserver(config)
    observation = observer.read()
    snapshot = catalog.snapshot()
    document = observer.state(observation, snapshot)
    business = json.loads(sql(observer, BUSINESS_SQL)); schema = json.loads(sql(observer, SCHEMA))
    request_count = sql(observer, 'SELECT count(*) FROM mp_operation_request;').strip()
    output.mkdir(parents=True)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    results = []
    for name, requested in [('labels', ['mp_example_notes_labels']), ('notes', ['mp_example_notes'])]:
        impact = observer.native_impact(observation, catalog, site_id=config['sites'][0]['site_id'], requested=requested)
        targets = [dict(installation_id=p['installation_id'], site_id=impact['site_id'], workspace_id=w,
                        plugin_id=p['plugin_id'], action='uninstall') for p in impact['plugins'] for w in p['workspace_ids']]
        bundle = prepare_current_image_uninstall(document, observation['sites'], snapshot, impact=impact,
            targets=targets, operation_id=str(uuid4()), created_at=now)
        independent = IndependentValidator(config, catalog_root, validator)
        assert independent(bundle) == document['state']
        assert check_bundle(bundle, document['state'])
        old = document['state']['release_lock']; new = bundle['operation_lock']['release']
        assert new['generation'] == 4 and new['created_at'] == now
        assert {k: v for k, v in old.items() if k not in ('generation', 'created_at', 'service_selection')} == {
            k: v for k, v in new.items() if k not in ('generation', 'created_at', 'service_selection')}
        removed_ids = {p['installation_id'] for p in impact['plugins']}
        surviving = [b for b in document['state']['bindings'] if not removed_ids.intersection(
            (b['consumer_installation_id'], b['provider_installation_id']))]
        assert bundle['operation_lock']['bindings'] == surviving
        assert len(bundle['plan']['permission_changes']) == sum(g['installation_id'] in removed_ids and g['state'] == 'approved'
                                                                 for g in observation['sites'][0]['grants'])
        # A fresh source observation after deleting only those bindings must
        # reconstruct the approved lock exactly, including abstract choices for
        # the retained source packages whose native schemas would be removed.
        projected_observation = copy.deepcopy(observation)
        projected_site = projected_observation['sites'][0]
        projected_site['bindings'] = [b for b in projected_site['bindings'] if b['descriptor'] in surviving]
        projected_config = copy.deepcopy(config)
        projected_config.update(generation=4, release_created_at=now)
        projected_config.pop('published_release', None)
        projected_document = DockerObserver(projected_config).state(projected_observation, snapshot)
        assert projected_document['state']['release_lock'] == new
        rejected = []
        for change in ('count_drift', 'old_epoch', 'source_change'):
            tampered = copy.deepcopy(bundle)
            if change == 'count_drift':
                assert tampered['operation_lock']['native_uninstall_impact']['fields']
                field = next(f for f in tampered['operation_lock']['native_uninstall_impact']['fields'] if f['non_null_records'] is not None)
                field['non_null_records'] += 1
            elif change == 'old_epoch': tampered['operation_lock']['release']['generation'] = 3
            else: tampered['operation_lock']['release']['core_inventory_digest'] = 'sha256:' + 'f'*64
            tampered['plan']['dependency_lock_digest'] = data_digest(tampered['operation_lock'])
            tampered['plan']['target_release_digest'] = data_digest(tampered['operation_lock']['release'])
            tampered['plan_hash'] = plan_hash(tampered['plan'])
            tampered['display'] = _display(tampered['plan'], tampered['operation_lock'])
            assert check_bundle(tampered, document['state'])
            try: independent(tampered)
            except ValueError: rejected.append(change)
            else: raise AssertionError('Rehashed tampering accepted: ' + change)
        (output / (name + '-bundle.json')).write_text(json.dumps(bundle, indent=2) + '\n', encoding='utf8')
        view = impact_view(impact, operation_id=bundle['plan']['operation_id'], plan_hash=bundle['plan_hash'], observed_at=now)
        (output / (name + '-impact.json')).write_text(json.dumps(view, indent=2) + '\n', encoding='utf8')
        results.append(dict(case=name, plan_hash=bundle['plan_hash'], operation_id=bundle['plan']['operation_id'],
            requested_addons=requested, native_closure=impact['native_closure'], target_count=len(targets),
            surviving_bindings=len(surviving), projected_generation=4, same_executable_inventory=True,
            explicit_revocations=len(bundle['plan']['permission_changes']),
            independent_reconstruction=True, post_binding_observation_matches=True, rehashed_tampering_rejected=rejected))
    assert observer.read() == observation
    assert json.loads(sql(observer, BUSINESS_SQL)) == business and json.loads(sql(observer, SCHEMA)) == schema
    assert sql(observer, 'SELECT count(*) FROM mp_operation_request;').strip() == request_count
    assert hashes == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    paths = ['packages/platform_sdk/modular_platform/' + p for p in ('plans.py', 'planning_cli.py', 'uninstall_planning.py',
        'lifecycle_impact.py', 'lifecycle_observation.py', 'deployment.py', 'approval_validation.py')]
    paths += ['tools/qualify_uninstall_plan.py', 'tests/test_uninstall_planning.py', 'tests/test_lifecycle_impact.py', 'tests/test_plans.py']
    report = dict(result='passed', scope='uninstall_planning_and_independent_read_only_reconstruction_only', utc=now,
        git_base=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}, image_id=config['image_id'],
        project=config['project'], generation=3, cases=results, before_after_observation_digest=data_digest(observation),
        before_after_business_digest=data_digest(business), before_after_schema_digest=data_digest(schema), protected_configs=hashes,
        application_request_count_unchanged=True, operator_request_approval_or_apply=False, runtime_activated=False,
        acceptance_credit=[], remaining='Authenticated preview/confirmation, same-executor native child, tombstones/reinstall, separate artifact-removal image and destructive lifecycle qualification.')
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: report[k] for k in ('result', 'scope', 'cases', 'runtime_activated')}))


if __name__ == '__main__': main()
