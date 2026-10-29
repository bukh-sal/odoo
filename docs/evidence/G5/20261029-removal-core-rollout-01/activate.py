"""Once-only exact core prerequisite on existing owned lifecycle6, never main.

Evidence driver only; uses the existing independent CLI/executor unchanged.
No prepare/apply replay or fixture bootstrap is supported.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local/g5-lifecycle'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk')); sys.path.insert(0, str(ROOT / 'tools'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql
from qualify_manager_upgrade_operation import files


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'apply']); args = parser.parse_args()
    target = LOCAL / 'operator/target.json'; marker = LOCAL / 'removal-core-upgrade.json'
    state = json.loads((LOCAL / 'state.json').read_text(encoding='utf8'))
    config = json.loads(target.read_text(encoding='utf8'))
    assert state['disposable'] and state['project'] == config['project'] == 'mp-r0-r1lifef99acae9d906'
    assert config['sites'][0]['database'] == state['active_db'] == 'mp_disposable_r0_r1_g5_life_f99acae9d906'
    assert config['generation'] == 6 and config['image_id'] == 'sha256:709d7fbd475aac6f2fef377b3f8d9a9bba15281931cc5e05b85f433ef7cdb708'
    assert state['phase'] == 'lifecycle_reinstalled_all_enabled'
    protected = [ROOT / '.local/operator/targets/g5.json', ROOT / '.local/g5-manager-upgrade/operator/target.json']
    protected_hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard():
        assert protected_hashes == {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        assert hashlib.sha256(protected[0].read_bytes()).hexdigest() == state['main_target_sha256']
    guard()
    build = json.loads((ROOT / 'docs/evidence/G5/20261029-removal-core-01/candidate-build.json').read_text(encoding='utf8'))
    assert build['result'] == 'built_not_deployed' and build['git_base'].startswith('1efd46de')
    for name, digest in build['source_sha256'].items(): assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    image = build['image_id']
    trust = ROOT / '.local/operator/trust.json'; catalog_root = ROOT / '.local/operator/catalog'; control = LOCAL / 'operator/control'
    validator = configuration(trust); catalog = Catalog(catalog_root, validator, readonly=True).snapshot(); reader = DockerObserver(config)
    observed = reader.read(); before = reader.state(observed, catalog)['state']
    business = json.loads(sql(reader, BUSINESS_SQL)); schema = json.loads(sql(reader, SCHEMA))
    assert len(business['notes']) == 4 and len(business['boards']) == 2 and len(before['installations']) == 6
    assert all(r['feature_state'] == 'enabled' for r in before['installations'])
    prefix = [sys.executable, 'tools/modular.py', '--config', str(trust)]
    options = ['--store', str(control), '--deployment-config', str(target), '--catalog', str(catalog_root)]
    def invoke(command):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=600)
        if result.returncode:
            private = LOCAL / ('core-cli-' + args.action + '.log'); private.write_bytes(result.stderr)
            raise RuntimeError('Independent CLI failed; inspect existing marker/journal/private diagnostics; never blindly retry')
        return json.loads(result.stdout)
    def write(name, value):
        with (OUTPUT / name).open('x', encoding='utf8') as stream: stream.write(json.dumps(value, indent=2) + '\n')
    if args.action == 'prepare':
        assert not marker.exists() and set(p.name for p in OUTPUT.iterdir()) == {'activate.py'}
        record = dict(state='preparing', base_generation=6, image_id=image, before_digest=data_digest(before), protected_config_hashes=protected_hashes)
        marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
        write('configuration-before.json', config); write('state-before.json', before); write('business-before.json', business)
        write('schema-before.json', schema); write('files-before.json', files(reader))
        write('staged-image.json', invoke(prefix + ['plugin', 'stage-image', '--image-id', image] + options))
        nomination = dict(operation_type='core_upgrade', targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')} | {'action':'deploy'} for r in before['installations']])
        write('nomination.json', nomination)
        bundle = invoke(prefix + ['plugin', 'plan-staged', '--input', str(OUTPUT / 'nomination.json')] + options)
        assert bundle['operation_lock']['native_core_changes'] == [
            dict(addon='mp_core', previous_version='19.0.0.1.5', target_version='19.0.0.1.6', migrations=[]),
            dict(addon='mp_shell', previous_version='19.0.0.1.6', target_version='19.0.0.1.7', migrations=[])]
        assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
        assert len(bundle['operation_lock']['targets']) == 6
        assert observed['runtime']['inventory']['artifacts'] == __import__('modular_platform.deployment', fromlist=['inspect_image']).inspect_image(image)['inventory']['artifacts']
        write('bundle.json', bundle); assert before == reader.state(reader.read(), catalog)['state']; guard()
        record.update(state='prepared_not_registered', operation_id=bundle['plan']['operation_id'], plan_hash=bundle['plan_hash'])
        marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8'); print(json.dumps(record)); return
    record = json.loads(marker.read_text(encoding='utf8'))
    assert record['state'] == 'prepared_not_registered' and record['image_id'] == image and record['before_digest'] == data_digest(before)
    assert record['protected_config_hashes'] == protected_hashes
    assert business == json.loads((OUTPUT / 'business-before.json').read_text(encoding='utf8'))
    assert schema == json.loads((OUTPUT / 'schema-before.json').read_text(encoding='utf8'))
    old_files = json.loads((OUTPUT / 'files-before.json').read_text(encoding='utf8')); assert old_files == files(reader)
    operation = record['operation_id']; operations = prefix + ['operations', '--store', str(control)]
    validation = ['--deployment-config', str(target), '--catalog', str(catalog_root)]
    def phase(value):
        record.update(state=value, utc=datetime.now(timezone.utc).isoformat()); marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    phase('registering'); write('registered.json', invoke(operations + ['register', '--bundle', str(OUTPUT / 'bundle.json')] + validation))
    review = invoke(operations + ['show', operation]); write('independent-review.json', review)
    assert review['plan_hash'] == record['plan_hash'] and review['phase'] == 'prepared' and review['state'] == 'awaiting_operator_approval'
    phase('approving'); write('approved.json', invoke(operations + ['approve', operation, '--plan-hash', record['plan_hash'], '--noninteractive', '--ack-trust', '--ack-destructive'] + validation))
    phase('applying'); status = StagedNativeExecutor(OperatorStore(control), target, catalog_root, validator).apply(operation)
    write('completed.json', status); assert status['state'] == 'completed'
    current = json.loads(target.read_text(encoding='utf8')); assert current['generation'] == 7 and current['image_id'] == image
    after_reader = DockerObserver(current); after_observation = after_reader.read(); after = after_reader.state(after_observation, catalog)['state']
    assert after['installations'] == before['installations'] and after['bindings'] == before['bindings']
    assert json.loads(sql(after_reader, BUSINESS_SQL)) == business and json.loads(sql(after_reader, SCHEMA)) == schema
    after_files = files(after_reader); assert all(after_files[name] == digest for name, digest in old_files.items())
    write('state-after.json', after); write('business-after.json', json.loads(sql(after_reader, BUSINESS_SQL)))
    write('schema-after.json', json.loads(sql(after_reader, SCHEMA))); write('files-after.json', after_files)
    guard(); state.update(phase='artifact_removal_core_ready', generation=7, image_id=image, worker_id=current['worker_id'])
    (LOCAL / 'state.json').write_text(json.dumps(state, indent=2) + '\n', encoding='utf8'); phase('completed_verified')
    write('activation.json', dict(result='passed_core_activation_only', utc=datetime.now(timezone.utc).isoformat(), operation_id=operation,
        plan_hash=record['plan_hash'], configuration=current, original_scope_bindings_grants_business_schema_exact=True,
        old_files_preserved=len(old_files), protected_config_hashes=protected_hashes,
        limits=['Actual uninstall/reinstall/HTTP/UI and asset lifecycle qualification remain pending; core activation is not LIFE acceptance.']))
    print(json.dumps(dict(result='completed_verified', operation_id=operation, generation=7, image_id=image)))


if __name__ == '__main__': main()
