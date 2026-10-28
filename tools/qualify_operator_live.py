"""Actual local CLI approval/revoke and application-container denial; never apply."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from observe_r1 import ROOT, OPERATOR, write_new
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest


def invoke(command, *, success=True):
    completed = subprocess.run(command, capture_output=True, timeout=90, cwd=ROOT)
    if (completed.returncode == 0) != success:
        raise RuntimeError('Unexpected bounded operator CLI outcome: ' + completed.stderr.decode(errors='replace')[:500])
    return json.loads(completed.stdout if success else completed.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'docs/evidence/G5') or output.exists():
        raise ValueError('Fresh G5 evidence directory required')
    output.mkdir(parents=True)
    invoke([sys.executable, 'tools/qualify_live_planning.py', '--output', str(output / 'draft')])
    bundle_path = output / 'draft/draft-bundle.json'
    bundle = json.loads(bundle_path.read_text())
    operation_id = bundle['plan']['operation_id']
    control = OPERATOR / 'control'
    prefix = [sys.executable, 'tools/modular.py', '--config', str(OPERATOR / 'trust.json'), 'operations', '--store', str(control)]
    target = str(OPERATOR / 'targets/r1.json')
    catalog = str(OPERATOR / 'catalog')
    if not control.exists():
        invoke(prefix + ['init-store', '--deployment-config', target, '--allow-noninteractive-disposable'])
    store = OperatorStore(control)
    if store.policy['allow_noninteractive'] is not True:
        raise RuntimeError('Existing operator policy does not enable this explicit unattended disposable test')
    registered = False
    try:
        initial = invoke(prefix + ['register', '--bundle', str(bundle_path), '--deployment-config', target, '--catalog', catalog])
        registered = True
        assert initial['state'] == 'awaiting_operator_approval'
        approve_args = ['approve', operation_id, '--deployment-config', target, '--catalog', catalog, '--noninteractive']
        wrong = invoke(prefix + approve_args + ['--plan-hash', 'sha256:' + '0' * 64], success=False)
        assert wrong['error'] == 'VALIDATION_FAILED' and 'Exact reviewed' in wrong['message']
        approved = invoke(prefix + approve_args + ['--plan-hash', bundle['plan_hash']])
        assert approved['state'] == 'approved' and approved['review']['display']['targets'] == bundle['display']['targets']
        write_new(output / 'approved-status.json', approved)
        config = json.loads(Path(target).read_text())
        observer = DockerObserver(config)
        app = observer._container('app')
        inspect = invoke(['docker', 'inspect', '--format', '{{json .Mounts}}', app])
        assert all(item['Type'] == 'volume' and item['Destination'] in ('/var/lib/modular', '/run/secrets') for item in inspect)
        readonly = invoke(['docker', 'inspect', '--format', '{{json .HostConfig.ReadonlyRootfs}}', app])
        assert readonly is True
        script = '''import json,os,pathlib,shutil
result={'uid':os.geteuid(),'docker_cli_available':shutil.which('docker') is not None,'docker_socket_present':pathlib.Path('/var/run/docker.sock').exists()}
for label,path in [('approval_read','/run/modular-operator/control.sqlite3'),('allowlist_read','/run/modular-operator/policy.json')]:
 try:
  with open(path,'rb') as stream:stream.read(1)
  result[label]={'allowed':True}
 except OSError as error:result[label]={'allowed':False,'errno':error.errno}
try:
 pathlib.Path('/run/modular-operator-denial-probe').mkdir()
 result['approval_store_creation']={'allowed':True}
except OSError as error:result['approval_store_creation']={'allowed':False,'errno':error.errno}
print(json.dumps(result))
'''
        denial = invoke(['docker', 'exec', app, '/venv/bin/python', '-c', script])
        assert denial['uid'] == 10001 and not denial['docker_cli_available'] and not denial['docker_socket_present']
        assert not any(denial[key]['allowed'] for key in ('approval_read', 'allowlist_read', 'approval_store_creation'))
        write_new(output / 'application-os-denial.json', {'observations': denial,
            'mount_destinations': sorted(item['Destination'] for item in inspect), 'readonly_rootfs': readonly,
            'control_store_namespace': 'Windows OS-owner DACL; not mounted into application container',
            'owner_acl_verified': True, 'operator_identity_kind': 'windows-sid' if sys.platform == 'win32' else 'posix-uid'})
    finally:
        if registered:
            revoked = invoke(prefix + ['revoke-approval', operation_id])
            write_new(output / 'revoked-status.json', revoked)
    assert revoked['state'] == 'revoked'
    config = json.loads(Path(target).read_text())
    trust = json.loads((OPERATOR / 'trust.json').read_text())
    validator = ArtifactValidator(TrustPolicy(approved_digests=frozenset(trust['approved_digests']), generation=trust['generation']))
    observer = DockerObserver(config)
    after = observer.state(observer.read(), Catalog(catalog, validator, readonly=True).snapshot())
    assert data_digest(after['state']) == bundle['plan']['base_state_digest']
    paths = ['packages/platform_sdk/modular_platform/' + name for name in ('operator_os.py', 'operator_store.py', 'approval_validation.py', 'plans.py')]
    paths += ['tools/modular.py', 'tools/qualify_operator_live.py']
    write_new(output / 'operator-live.json', {'result': 'passed', 'item': 'E-01c-live-approval',
        'utc': datetime.now(timezone.utc).isoformat(), 'operation_id': operation_id, 'plan_hash': bundle['plan_hash'],
        'final_approval_state': 'revoked', 'database_mutations': False, 'apply': False,
        'observations': ['OS-owned external allowlist/store initialized once with exact disposable target IDs.',
            'Real CLI independently re-observed deployment/catalog and reconstructed feature plan before registration and approval.',
            'Wrong exact hash denied; valid exact hash approved under explicit noninteractive disposable policy.',
            'Real application UID10001 has no operator-store mount, Docker socket/CLI or writable control namespace.',
            'Approval revoked in finally; current application authority unchanged.'],
        'limitations': ['No native execution, backup or restore yet.', 'UI queue/status adapter and code-changing staged-release validation remain E-01c/d.'],
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}})
    print(json.dumps({'result': 'passed', 'item': 'E-01c-live-approval', 'evidence': str(output), 'final_approval_state': 'revoked', 'apply': False}))


if __name__ == '__main__':
    main()
