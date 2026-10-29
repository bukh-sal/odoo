"""Read-only current-image/source qualification of G5 uninstall impact.

No bootstrap, native ORM import, approval, execution, seeding or target writes.
New inspector source is evaluated in a separate Python process, not installed
into the running application. Only the explicitly owned lifecycle fixture is read.
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
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_impact import check_impact_view, impact_view, verified_archive_sources
from modular_platform.plans import data_digest
from modular_platform.projection import runtime_inputs
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql


CHILD = r'''
import configparser, hashlib, json, pathlib, sys, types
import psycopg2
data=json.load(sys.stdin)
module=types.ModuleType('modular_platform.lifecycle_impact')
module.__package__='modular_platform'
exec(compile(data['inspector'],'reviewed-lifecycle-impact.py','exec'),module.__dict__)
root=pathlib.Path('/opt/modular')
inventory=json.loads((root/'distribution-inventory.json').read_text())
addons={'mp_identity'}|{d['manifest']['runtime']['addon_name'] for d in data['descriptors']}
sources={}
for path,digest in inventory['files'].items():
 if path.startswith('addons/') and path.endswith('.py') and path.split('/')[1] in addons:
  raw=(root/path).read_bytes()
  assert hashlib.sha256(raw).hexdigest()==digest,'Actual image source drift'
  sources[path[len('addons/'):]]=raw
for path,expected in data['archive_sources'].items():
 assert hashlib.sha256(sources[path]).hexdigest()==expected,'Catalog to actual-image source mismatch'
cfg=configparser.ConfigParser();cfg.read('/run/secrets/odoo_config');opts=cfg['options']
assert opts['db_name']==data['database'],'Wrong disposable database'
connection=psycopg2.connect(host=opts['db_host'],port=opts.getint('db_port'),user=opts['db_user'],
 password=opts['db_password'],dbname=opts['db_name'],connect_timeout=10)
connection.set_session(isolation_level='REPEATABLE READ',readonly=True)
results={}
with connection:
 with connection.cursor() as cursor:cursor.execute("SET LOCAL statement_timeout='5s'")
 for name,requested in data['cases'].items():
  results[name]=module.inspect_native_impact(connection,site_id=data['site_id'],requested=requested,
    descriptors=data['descriptors'],sources=sources)
 try:
  module.inspect_native_impact(connection,site_id='00000000-0000-0000-0000-000000000000',
    requested=data['cases']['labels'],descriptors=data['descriptors'],sources=sources)
 except module.PlanningError:results['wrong_site_rejected']=True
 else:raise AssertionError('Cross-site preview accepted')
connection.set_session(isolation_level='READ COMMITTED',readonly=False)
with connection:
 with connection.cursor() as cursor:cursor.execute("SET LOCAL statement_timeout='5s'")
 try:
  module.inspect_native_impact(connection,site_id=data['site_id'],requested=data['cases']['labels'],
    descriptors=data['descriptors'],sources=sources)
 except module.PlanningError:results['unsafe_transaction_rejected']=True
 else:raise AssertionError('Unbounded mutable snapshot accepted')
connection.close()
assert 'odoo' not in sys.modules,'Native registry must not be imported'
print(json.dumps({'results':results,'source_files':len(sources),'native_registry_imported':False}))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
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
    catalog = Catalog(ROOT / '.local/operator/catalog', configuration(ROOT / '.local/operator/trust.json'), readonly=True)
    observer = DockerObserver(config)
    before = observer.read()
    business_before = json.loads(sql(observer, BUSINESS_SQL))
    schema_before = json.loads(sql(observer, SCHEMA))
    baseline = json.loads((local / 'lifecycle-data.json').read_text(encoding='utf8'))
    assert schema_before == baseline['schema']
    assert {k: v for k, v in business_before.items() if k != 'features'} == {
        k: v for k, v in baseline['business'].items() if k != 'features'}
    non_null_labels = sum(note['x_notes_labels'] is not None for note in business_before['notes'])
    selected, _, _ = runtime_inputs(before['runtime'], catalog.snapshot())
    sources = {}
    for descriptor in selected:
        sources.update(verified_archive_sources(catalog.path(descriptor['digest']), descriptor))
    module_path = ROOT / 'packages/platform_sdk/modular_platform/lifecycle_impact.py'
    cases = {'labels': ['mp_example_notes_labels'], 'notes': ['mp_example_notes'], 'canvas': ['mp_example_canvas']}
    request = dict(inspector=module_path.read_text(encoding='utf8'), descriptors=selected,
                   archive_sources={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
                   site_id=config['sites'][0]['site_id'], database=state['active_db'], cases=cases)
    output.mkdir(parents=True)
    result = subprocess.run(['docker', 'exec', '-i', observer._container('app'), '/venv/bin/python', '-c', CHILD],
                            input=json.dumps(request).encode(), capture_output=True, timeout=90)
    # Keep stderr private: a failed process can include connection diagnostics.
    private = local / ('impact-inspection-' + str(uuid4()) + '.log')
    if result.returncode:
        private.write_bytes(result.stderr)
        raise RuntimeError('Read-only inspector failed; private diagnostics: ' + str(private))
    observed = json.loads(result.stdout)
    (output / 'observed.json').write_text(json.dumps(observed, indent=2) + '\n', encoding='utf8')
    values = observed['results']
    assert values['wrong_site_rejected'] and values['unsafe_transaction_rejected']
    assert values['labels']['native_closure'] == ['mp_example_notes_labels']
    assert values['notes']['native_closure'] == ['mp_example_canvas', 'mp_example_notes', 'mp_example_notes_labels']
    assert values['canvas']['native_closure'] == ['mp_example_canvas']
    labels = values['labels']
    assert not labels['models'], 'Shared Notes model must not be reported as exclusively owned by Labels'
    assert [(f['model'], f['field'], f['relation'], f['non_null_records']) for f in labels['fields']] == [
        ('mp.example.note', 'x_notes_labels', 'mp_example_note', non_null_labels)]
    assert len(labels['plugins'][0]['workspace_ids']) == 2
    assert all(v['dispatch'] == dict(state='not_present', tables=[]) for v in (values[name] for name in cases))
    assert {m['model']: m['records'] for m in values['notes']['models']} == {
        'mp.example.note': 4, 'mp.example.canvas.board': 2}
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    for name in cases:
        # Synthetic identity only tests DTO binding. No executable proposal exists.
        view = impact_view(values[name], operation_id=str(uuid4()), plan_hash='sha256:' + '0'*64, observed_at=now)
        check_impact_view(view, operation_id=view['operation_id'], plan_hash=view['plan_hash'], expected_impact_digest=data_digest(values[name]))
        (output / (name + '-impact.json')).write_text(json.dumps(view, indent=2) + '\n', encoding='utf8')
    after = observer.read()
    assert before == after, 'Read-only preview changed deployment/native/security metadata'
    assert json.loads(sql(observer, BUSINESS_SQL)) == business_before
    assert json.loads(sql(observer, SCHEMA)) == schema_before
    assert hashes == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    source_paths = [module_path, Path(__file__), ROOT / 'tests/test_lifecycle_impact.py']
    report = dict(result='passed', scope='read_only_inspector_source_integration_only', utc=now,
                  project=config['project'], generation=config['generation'], image_id=config['image_id'],
                  sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
                  inspected_image_source_files=observed['source_files'], catalog_source_files=len(sources),
                  before_after_metadata_digest=data_digest(before), protected_config_hashes=hashes,
                  before_after_business_digest=data_digest(business_before), before_after_schema_digest=data_digest(schema_before),
                  labels_non_null_records=non_null_labels,
                  checks=['actual three dependency closures', 'shared model/fields retained', 'Labels one stored field/count matches independent retained business data',
                          'Notes+Canvas two models/six records', 'both workspaces covered', 'constraints/references/assets',
                          'unknown fields explicit', 'no dispatch tables', 'wrong-site rejection', 'unsafe transaction rejection',
                          'no native registry import', 'strict bound DTO', 'exact unchanged deployment observation/configs'],
                  runtime_activated=False, approval_or_native_execution=False, acceptance_credit=[],
                  remaining='Impact endpoint/operation-lock independent reconstruction, actual native uninstall/reinstall/artifact removal and destructive lifecycle qualification.')
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
