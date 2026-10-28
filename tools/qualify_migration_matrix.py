"""Once-only G5 native-engine migration matrix; never a deployment executor.

Verified development archives are extracted to a new read-only fixture volume.
Only new, ownership-marked databases on the existing disposable fixture server
are used. The real manager/approval path is qualified separately on Notes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/g5-migration-matrix'
OUTPUT = ROOT / 'docs/evidence/G5/20261029-migration-matrix-01'
IMAGE = 'sha256:0afd445cb1147de1fbf18ba250a5b7346570c21da26fb2b0d1ea4f78134a1319'
ADDON = 'mp_g5_migration_probe'
PLUGIN = 'org.test.migration_probe'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.contracts import normalize_manifest
from modular_platform.deployment import DockerObserver
from modular_platform.plans import applicable_migrations
from packaging.version import Version
from qualify_manager_upgrade_operation import snapshot
from reference_package import toml_value


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def run(argv, *, raw=None):
    process = subprocess.run(argv, input=raw, capture_output=True, cwd=ROOT, timeout=600)
    if process.returncode:
        raise RuntimeError('Fixture command failed: ' + process.stderr.decode(errors='replace')[-1800:])
    return process.stdout


def script(version, phase):
    # These steps deliberately require reconciliation rather than blind replay.
    return f'''# Repository-owned disposable G5 migration witness. LGPL-3.0-only.
import hashlib, json
def migrate(cr, version):
    target = {version!r}
    phase = {phase!r}
    cr.execute("SELECT count(*) FROM mp_g5_migration_event WHERE target=%s AND phase=%s", [target,phase])
    assert cr.fetchone()[0] == 0, 'Non-retryable fixture step already ran; reconcile'
    cr.execute("SELECT id,name,payload,step_count FROM mp_g5_migration_record ORDER BY id")
    before = cr.fetchall()
    assert len(before) == 2, 'Expected explicit baseline and user fixture'
    cr.execute("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='mp_g5_migration_record' AND column_name='current_ready')")
    ready = cr.fetchone()[0]
    cr.execute("UPDATE mp_g5_migration_record SET payload=payload || %s, step_count=step_count+1", ['|'+phase+'@'+target])
    cr.execute("SELECT id,name,payload,step_count FROM mp_g5_migration_record ORDER BY id")
    after = cr.fetchall()
    digest = lambda rows: hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    cr.execute("INSERT INTO mp_g5_migration_event (phase,target,installed,payload_before,payload_after,column_ready) VALUES (%s,%s,%s,%s,%s,%s)", [phase,target,version,digest(before),digest(after),ready])
'''.encode()


def artifact(version, directory):
    evolved = Version(version) >= Version('0.2.0')
    prefix = 'backend/odoo_addons/' + ADDON + '/'
    native = {'name': 'G5 migration probe', 'version': '19.0.' + version,
              'license': 'LGPL-3', 'depends': ['base'], 'data': ['data.xml'],
              'installable': True, 'application': False, 'auto_install': False}
    models = '''from odoo import fields,models
class Record(models.Model):
    _name='mp.g5.migration.record'
    _description='Disposable migration record'
    name=fields.Char(required=True)
    payload=fields.Text(required=True)
    step_count=fields.Integer(default=0)
'''
    if evolved:
        models += '    current_ready=fields.Boolean(default=True)\n'
    models += '''class Event(models.Model):
    _name='mp.g5.migration.event'
    _description='Disposable non-replayable migration event'
    phase=fields.Char(required=True)
    target=fields.Char(required=True)
    installed=fields.Char(required=True)
    payload_before=fields.Char(required=True)
    payload_after=fields.Char(required=True)
    column_ready=fields.Boolean()
'''
    files = {prefix + '__manifest__.py': repr(native).encode(),
             prefix + '__init__.py': b'from . import models\n', prefix + 'models.py': models.encode(),
             prefix + 'data.xml': (f'<odoo noupdate="1"><record id="baseline" model="mp.g5.migration.record">'
                                  f'<field name="name">Baseline fixture</field><field name="payload">fresh:{version}</field>'
                                  '</record></odoo>').encode(), 'notices/LICENSE': (ROOT / 'LICENSE').read_bytes()}
    transitions = []
    pairs = [('0.1.0', '0.1.9'), ('0.1.9', '0.1.10'), ('0.1.10', '0.2.0'),
             ('0.2.0', '0.3.0'), ('0.99999998.0', '0.99999999.0'), ('0.99999999.0', '0.100000000.0')]
    for start, target in pairs:
        if Version(target) > Version(version):
            continue
        scripts = []
        for phase in ('pre', 'post', 'end'):
            path = f'migrations/19.0.{target}/{phase}-witness.py'
            files[prefix + path] = script(target, phase)
            scripts.append({'path': path, 'digest': 'sha256:' + sha(files[prefix + path]), 'phase': phase})
        transitions.append({'from': start, 'to': target, 'scripts': scripts,
            'preconditions': ['Dedicated marked database; two fixture rows; no repeated step'],
            'postconditions': ['Both rows retain identity/name and gain exactly one payload token/event per script'],
            'retry': 'reconcile', 'recovery': 'Do not replay uncertain native processes; inspect retained child and SQL witnesses. Restore coordinated checkpoint for real operations; this fixture has no external side effects.'})
    manifest = normalize_manifest({'schema_version': 1,
        'plugin': {'id': PLUGIN, 'version': version, 'name': 'G5 migration fixture', 'description': 'Native engine test only', 'publisher': 'test', 'license': 'LGPL-3.0-only'},
        'compatibility': {'platform': '>=0.1,<0.2', 'host_api_major': 1, 'ui_api_major': 1},
        'runtime': {'kind': 'native', 'addon_name': ADDON, 'native_compatibility': 'odoo-19', 'python': '>=3.12,<3.13', 'python_dependencies': []},
        'activation': {'scopes': ['site'], 'supports_feature_suspension': False},
        'data': {'models': ['mp.g5.migration.record', 'mp.g5.migration.event'], 'extension_targets': [], 'contributions': []},
        'upgrade': {'strategy': 'native_migrations', 'requires_maintenance': True, 'destructive': False, 'transitions': transitions}})
    files['plugin.toml'] = ('\n'.join(json.dumps(k) + ' = ' + toml_value(v) for k, v in manifest.items()) + '\n').encode()
    files['provenance.json'] = json.dumps({'schema_version': 1, 'builder': 'g5-native-matrix-fixture-v1', 'source_files': {k: sha(v) for k, v in sorted(files.items())}}).encode()
    files['inventory.json'] = json.dumps({'schema_version': 1, 'excluded': ['inventory.json'], 'files': {k: sha(v) for k, v in sorted(files.items())}}).encode()
    archive = directory / (version + '.mplug')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as out:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(PLUGIN + '/' + name, (2000, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o444) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, raw)
    validator = ArtifactValidator(TrustPolicy('development', allow_unsigned_development=True))
    extracted, verified = validator.stage(archive, directory, expected_digest='sha256:' + sha(archive.read_bytes()))
    payload = {}
    with extracted:
        base = Path(extracted.name) / 'payload' / prefix
        for path in sorted(base.rglob('*')):
            if path.is_file():
                relative = path.relative_to(base).as_posix()
                raw = path.read_bytes()
                assert sha(raw) == verified.inventory[prefix + relative]
                payload[version + '/' + ADDON + '/' + relative] = raw
    return manifest, payload, {'version': version, 'artifact_digest': verified.digest, 'native_manifest': native,
        'scripts': [{'path': k, 'sha256': sha(v)} for k, v in files.items() if '/migrations/' in k],
        'schema_source_sha256': sha(models.encode()), 'declared_recovery': [t['recovery'] for t in transitions]}


def main():
    global LOCAL, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', required=True)
    parser.add_argument('--attempt', choices=['01', '02'], default='01')
    args = parser.parse_args()
    if args.attempt == '02':
        prior = json.loads((LOCAL / 'state.json').read_text())
        assert prior['phase'] == 'terminal_cli_parse_failure_no_native_mutation' and prior['reconciliation']['user_tables'] == 0
        LOCAL = ROOT / '.local/g5-migration-matrix-02'
        OUTPUT = ROOT / 'docs/evidence/G5/20261029-migration-matrix-02'
    if LOCAL.exists() or OUTPUT.exists():
        raise RuntimeError('Once-only matrix exists; inspect its state/children instead of replaying')
    target = ROOT / '.local/g5-manager-upgrade/operator/target.json'
    configuration = json.loads(target.read_text())
    assert configuration['project'] == 'mp-r0-r1mgr84459f617ab0' and configuration['generation'] == 5 and configuration['image_id'] == IMAGE
    local_state = json.loads((ROOT / '.local/g5-manager-upgrade/state.json').read_text())
    assert local_state['disposable'] is True
    guards = {}
    for name, path in [('main', ROOT / '.local/operator/targets/g5.json'), ('manager', target)]:
        config = json.loads(path.read_text())
        observer = DockerObserver(config)
        guards[name] = {'path': str(path), 'configuration_sha256': sha(path.read_bytes()), 'business': snapshot(observer)}
    LOCAL.mkdir(parents=True)
    OUTPUT.mkdir(parents=True)
    project = 'mp-g5-matrix-' + uuid.uuid4().hex[:12]
    state = {'phase': 'preparing', 'project': project, 'image_id': IMAGE, 'databases': {}, 'children': [], 'disposable': True, 'guards': guards}
    state_path = LOCAL / 'state.json'
    def phase(value):
        state['phase'] = value
        write(state_path, state)
    phase('preparing')
    versions = ['0.1.0', '0.1.9', '0.1.10', '0.2.0', '0.3.0', '0.99999998.0', '0.100000000.0']
    manifests, payload, records = {}, {}, []
    for version in versions:
        manifest, contents, record = artifact(version, LOCAL)
        manifests[version] = manifest
        payload.update(contents)
        records.append(record)
    write(OUTPUT / 'validated-archives.json', records)
    tar_raw = io.BytesIO()
    with tarfile.open(fileobj=tar_raw, mode='w') as tar:
        for name, raw in sorted(payload.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(raw), 0o444
            tar.addfile(info, io.BytesIO(raw))
    volume = project + '-sources'
    state['source_volume'] = volume
    phase('creating_source_volume')
    run(['docker', 'volume', 'create', '--label', 'com.modular.disposable=' + project, volume])
    runner = "import os,sys,tarfile; os.umask(0o022); a=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); a.extractall('/matrix',filter='data')"
    run(['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only', '--user', '0:0', '--mount', 'type=volume,source=' + volume + ',target=/matrix', '--entrypoint', '/venv/bin/python', IMAGE, '-c', runner], raw=tar_raw.getvalue())
    db_container = configuration['project'] + '-db-1'
    def sql(database, query):
        return run(['docker', 'exec', '-i', db_container, 'psql', '-X', '-qAt', '-U', 'postgres', '-d', database, '-v', 'ON_ERROR_STOP=1'], raw=query.encode())
    def new_database(case):
        database = 'mp_disposable_g5_matrix_' + project.rsplit('-', 1)[-1] + '_' + case
        assert re.fullmatch(r'mp_disposable_g5_matrix_[a-z0-9_]+', database)
        assert sql('postgres', f"SELECT count(*) FROM pg_database WHERE datname='{database}';").strip() == b'0'
        state['databases'][case] = database
        phase('creating_database_' + case)
        sql('postgres', f'CREATE DATABASE "{database}" OWNER modular TEMPLATE template0 ENCODING \'UTF8\'; COMMENT ON DATABASE "{database}" IS \'{project}\';')
        return database
    def inspect(database):
        query = """BEGIN READ ONLY; SELECT jsonb_build_object(
          'native_version',(SELECT latest_version FROM ir_module_module WHERE name='mp_g5_migration_probe'),
          'native_state',(SELECT state FROM ir_module_module WHERE name='mp_g5_migration_probe'),
          'rows',(SELECT jsonb_agg(jsonb_build_object('id',id,'name',name,'payload',payload,'step_count',step_count) ORDER BY id) FROM mp_g5_migration_record),
          'events',COALESCE((SELECT jsonb_agg(jsonb_build_object('phase',phase,'target',target,'installed',installed,'payload_before',payload_before,'payload_after',payload_after,'column_ready',column_ready) ORDER BY id) FROM mp_g5_migration_event),'[]'::jsonb),
          'columns',(SELECT jsonb_agg(jsonb_build_array(column_name,data_type,is_nullable) ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='mp_g5_migration_record'));
          ROLLBACK;"""
        return json.loads(sql(database, query))
    def native(case, database, version, action, label):
        assert sql('postgres', f"SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='{database}';").strip().decode() == project
        name = project + '-' + label
        command = ['docker', 'create', '--name', name, '--label', 'com.modular.disposable=' + project,
            '--read-only', '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '768m', '--cpus', '2', '--pids-limit', '128', '--network', configuration['project'] + '_runtime',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m,mode=1777',
            '--mount', 'type=volume,source=' + volume + ',target=/matrix,readonly',
            '--mount', 'type=volume,source=' + configuration['project'] + '_appconfig,target=/run/secrets,readonly',
            '--entrypoint', '/venv/bin/python', IMAGE, '/opt/modular/odoo-bin', '-c', '/run/secrets/odoo_config', '-d', database,
            '--db-filter=^' + database + '$', '--data-dir=/tmp/native-data', '--workers=0', '--max-cron-threads=0', '--no-http',
            '--stop-after-init', '--without-demo', '--load=base',
            '--addons-path=/opt/modular/addons,/matrix/' + version, action, ADDON]
        state['children'].append({'name': name, 'case': case, 'database': database, 'version': version, 'action': action, 'state': 'nominated'})
        phase('native_' + label)
        run(command)
        process = subprocess.run(['docker', 'start', '-a', name], cwd=ROOT, capture_output=True, timeout=240)
        (OUTPUT / (label + '.log')).write_bytes(process.stdout + process.stderr)
        observed = json.loads(run(['docker', 'inspect', name]))[0]
        state['children'][-1].update({'state': observed['State']['Status'], 'exit_code': observed['State']['ExitCode']})
        write(OUTPUT / (label + '-child.json'), {'name': name, 'image_id': observed['Image'], 'arguments': observed['Config']['Cmd'], 'exit_code': observed['State']['ExitCode']})
        phase('native_' + label + '_terminal')
        assert process.returncode == observed['State']['ExitCode'] == 0 and observed['Image'] == IMAGE, 'Inspect retained child/log; never repeat native process blindly'
        result = inspect(database)
        assert result['native_version'] == '19.0.' + version and result['native_state'] == 'installed'
        write(OUTPUT / (label + '.json'), result)
        print(json.dumps({'stage': label, 'version': version, 'events': len(result['events']), 'native_exit': 0}), flush=True)
        return result
    results, discrepancies = [], []
    for case, start, targets in [('adjacent', '0.1.9', ['0.1.10', '0.2.0']), ('skipped', '0.1.0', ['0.3.0']), ('wide', '0.99999998.0', ['0.100000000.0']), ('fresh', '0.3.0', [])]:
        database = new_database(case)
        before = native(case, database, start, '-i', case + '-install')
        assert before['events'] == [] and len(before['rows']) == 1 and before['rows'][0]['payload'] == 'fresh:' + start and before['rows'][0]['step_count'] == 0
        assert ('current_ready' in [r[0] for r in before['columns']]) == (Version(start) >= Version('0.2.0'))
        if not targets:
            results.append({'case': case, 'database': database, 'fresh_current_schema_data_without_upgrade_events': True})
            continue
        phase('seeding_' + case)
        sql(database, "INSERT INTO mp_g5_migration_record (name,payload,step_count) VALUES ('User fixture','user-original',0);")
        prior = inspect(database)
        previous = start
        for target_version in targets:
            selected = applicable_migrations(manifests[target_version], previous)
            ordered = sorted(selected, key=lambda item: ({'pre': 0, 'post': 1, 'end': 2}[item['phase']], Version(item['target_version']), Path(item['path']).name))
            expected = [(item['phase'], item['target_version']) for item in ordered]
            after = native(case, database, target_version, '-u', case + '-upgrade-' + target_version.replace('.', '_'))
            events = after['events'][len(prior['events']):]
            assert [(e['phase'], e['target']) for e in events] == expected
            assert all(e['installed'] == '19.0.' + previous for e in events)
            suffix = ''.join('|' + phase + '@' + version for phase, version in expected)
            assert len(prior['rows']) == len(after['rows']) == 2
            for old, new in zip(prior['rows'], after['rows']):
                assert (old['id'], old['name']) == (new['id'], new['name'])
                assert new['payload'] == old['payload'] + suffix and new['step_count'] == old['step_count'] + len(expected)
            assert all(a['payload_after'] == b['payload_before'] for a, b in zip(events, events[1:]))
            if Version(previous) < Version('0.2.0') <= Version(target_version):
                assert all(e['column_ready'] == (e['phase'] != 'pre') for e in events)
            else:
                assert all(e['column_ready'] == (Version(previous) >= Version('0.2.0')) for e in events)
            declared = [(item['phase'], item['target_version']) for item in selected]
            if declared != expected:
                discrepancies.append({'case': case, 'from': previous, 'to': target_version, 'planner_recorded_order': declared, 'actual_native_order': expected})
            results.append({'case': case, 'database': database, 'from': previous, 'to': target_version, 'executed_scripts': len(events), 'data_identity_preserved': True, 'schema_before_sha256': sha(json.dumps(prior['columns']).encode()), 'schema_after_sha256': sha(json.dumps(after['columns']).encode()), 'native_order_matches_declared_hash_set': True})
            prior, previous = after, target_version
    for guard in guards.values():
        path = Path(guard['path'])
        assert sha(path.read_bytes()) == guard['configuration_sha256'] and snapshot(DockerObserver(json.loads(path.read_text()))) == guard['business']
    report = {'result': 'passed_native_engine_matrix' if not discrepancies else 'native_engine_passed_planner_order_mismatch',
        'utc': datetime.now(timezone.utc).isoformat(), 'source_commit': run(['git', 'rev-parse', 'HEAD']).decode().strip(),
        'image_id': IMAGE, 'fixture_source_sha256': sha(Path(__file__).read_bytes()), 'project': project, 'cases': results,
        'planner_order_discrepancies': discrepancies, 'existing_targets_configuration_business_unchanged': True,
        'limits': ['Direct native-engine harness with verified development archives, not an additional manager/independent approval proof. Retained actual Notes first-native/adjacent operations supply that control-path evidence.',
                   'No failure/crash/recovery claim from this matrix; those remain G5-X06/X09. Non-retryable witnesses require reconciliation after uncertainty.',
                   'No existing database/volume reset; no Canvas/product/UI changes.']}
    write(OUTPUT / 'qualification.json', report)
    phase(report['result'])
    print(json.dumps({'result': report['result'], 'cases': len(results), 'planner_discrepancies': len(discrepancies), 'project': project}), flush=True)


if __name__ == '__main__':
    main()
