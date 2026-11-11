"""Build an exact clean package-subtraction image; never uninstall or deploy.

The source image supplies immutable payload/dependency bytes, not final ancestry.
Normal stage/review/approval and complete database checks remain separate.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'packages/platform_sdk')]
from build_candidate import _clean_inputs, _verify_clean_rtl
from application_package import source_path
from modular_platform.artifact_removal import validate_removal_image
from modular_platform.contracts import checked_path
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import ProcessLock, protect_directory
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest

IMAGE = re.compile(r'sha256:[0-9a-f]{64}')
EXTRA_FILES = {'distribution-inventory.json', 'startup-profile', 'requirements.lock'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_record(path, image, runtime, clean):
    record = json.loads(Path(path).read_bytes())
    inventory = runtime['inventory']
    if (record.get('state') != 'built' or record.get('result') != 'built_not_deployed'
            or record.get('build_mode') != 'clean'
            or record.get('docker_target') != 'clean-runtime'
            or record.get('image_id') != image
            or record.get('inventory_digest') != runtime['inventory_digest']
            or record.get('artifacts') != inventory.get('artifacts', {})):
        raise ValueError('Exact successful clean source build record/image/inventory required')
    for key in ('python_image', 'python_version', 'debian_snapshot', 'dockerfile_sha256',
                'runtime_requirements_sha256', 'rtl_node_image', 'rtl_node_version',
                'rtlcss_version', 'rtl_package_lock_sha256', 'rtl_package_sha256', 'rtl_wrapper_sha256'):
        if record.get(key) != clean[key]:
            raise ValueError('Clean source dependency input changed: ' + key)
    if runtime['python_lock_digest'] != clean['runtime_requirements_sha256']:
        raise ValueError('Source runtime dependency lock differs from reviewed clean inputs')
    if any(runtime.get(k) for k in ('modified_files', 'missing_addon_files', 'unexpected_addon_files')):
        raise ValueError('Exact inventoried source image required')
    policy = inventory['policy']
    if (policy.get('runtime_surface') != 'clean' or policy.get('platform_sdk') is not True
            or policy.get('stock_webclient') is not True):
        raise ValueError('Qualified clean native-package composition required')
    if not isinstance(record.get('source_sha256'), dict) or not record['source_sha256']:
        raise ValueError('Source payload build provenance is missing')
    return record


def subtract_inventory(base, packages, package_sources=None):
    """Derive data only; use the same exact-delta guard as the independent planner."""
    inventory = copy.deepcopy(base['inventory'])
    artifacts = inventory.get('artifacts', {})
    if (not packages or len(set(packages)) != len(packages)
            or not set(packages) <= artifacts.keys()):
        raise ValueError('Unique present package IDs required')
    addons = {artifacts[p]['addon'] for p in packages}
    if (len(addons) != len(packages)
            or any(not re.fullmatch(r'[a-z][a-z0-9_]*', a) for a in addons)):
        raise ValueError('Distinct native package addons required')
    source_keys = ('reference_packages', 'application_packages')
    paths = [p for key in source_keys for p in inventory['policy'].get(key, [])]
    if len(paths) != len(artifacts) or len(set(paths)) != len(paths):
        raise ValueError('Unambiguous package source provenance required')
    if set(packages) == artifacts.keys():
        retained_paths = []
    else:
        if (package_sources is None or set(package_sources) != set(paths)
                or set(package_sources.values()) != set(artifacts)):
            raise ValueError('Exact source-manifest identity map required for partial subtraction')
        retained_paths = [p for p in paths if package_sources[p] not in packages]
    removed = set()
    for plugin in packages:
        item = artifacts.pop(plugin)
        archive = 'artifacts/' + checked_path(item['file'])
        if '/' in item['file']:
            raise ValueError('Exact top-level package archive filename required')
        prefix = 'addons/' + item['addon'] + '/'
        selected = {p for p in inventory['files'] if p.startswith(prefix)}
        if not selected or archive not in inventory['files']:
            raise ValueError('Package archive or native source is missing')
        removed.update(selected | {archive})
        inventory['native_addons'].pop(item['addon'])
    inventory['files'] = {p: h for p, h in inventory['files'].items() if p not in removed}
    policy = inventory['policy']
    for key in ('addons', 'explicit_install'):
        policy[key] = [a for a in policy[key] if a not in addons]
    for key in source_keys:
        if key in policy:
            policy[key] = [p for p in policy[key] if p in retained_paths]
    if not artifacts:
        inventory.pop('artifacts', None)
    for key in ('reference_composition', 'package_composition'):
        if not artifacts:
            inventory.pop(key, None)
        elif key in inventory:
            composition = inventory[key]
            for name in ('models', 'fields'):
                composition[name] = {p: owner for p, owner in composition[name].items() if owner not in packages}
            composition['ui_contributions'] = [p for p in composition['ui_contributions']
                if not any(p.startswith(plugin + ':') for plugin in packages)]
    candidate = copy.deepcopy(base)
    candidate['inventory'] = inventory
    candidate['native_manifests'] = {a: m for a, m in base['native_manifests'].items() if a not in addons}
    candidate['inventory_digest'] = 'sha256:' + hashlib.sha256(inventory_bytes(inventory)).hexdigest()
    descriptor = dict(base_image_id='sha256:' + '0' * 64, target_image_id='sha256:' + '1' * 64,
        inventory_digest=candidate['inventory_digest'], runtime_digest=data_digest(candidate))
    diff = validate_removal_image(base, candidate, descriptor, packages)
    return inventory, diff


def inventory_bytes(inventory):
    return (json.dumps(inventory, indent=2, sort_keys=True) + '\n').encode()


def render_dockerfile(root, clean):
    original = (root / 'deploy/Dockerfile').read_text(encoding='utf8')
    marker = 'FROM ${PYTHON_IMAGE} AS clean-runtime\n'
    boundary = 'COPY --from=builder /venv /venv\n'
    if original.count(marker) != 1 or original.count(boundary) != 2:
        raise ValueError('Reviewed clean runtime recipe boundaries changed')
    recipe = original.split(marker)[1].split(boundary)[0]
    if re.search(r'(?m)^(FROM|COPY|ADD)\b', recipe):
        raise ValueError('Clean OS recipe cannot copy or inherit another source')
    return ('ARG PYTHON_IMAGE=' + clean['python_image'] + '\n'
        'ARG DEPENDENCY_IMAGE\nFROM ${DEPENDENCY_IMAGE} AS dependency-input\n'
        'FROM ${PYTHON_IMAGE} AS clean-subtraction\n' + recipe +
        'COPY --from=dependency-input /venv /venv\n'
        'COPY release /opt/modular\n'
        'COPY --from=dependency-input /usr/local/bin/node /usr/local/bin/node\n'
        'COPY --from=dependency-input /opt/stock-rtl /opt/stock-rtl\n'
        'COPY --from=dependency-input /usr/local/bin/rtlcss /usr/local/bin/rtlcss\n'
        'WORKDIR /opt/modular\nUSER 10001:10001\nEXPOSE 8069\n'
        'ENTRYPOINT ["/venv/bin/python", "/opt/modular/tools/start_worker.py"]\n'
        'CMD ["-c", "/run/secrets/odoo_config"]\n')


def prepare_payload(release, before, after):
    entries = list(release.rglob('*'))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in entries):
        raise ValueError('Linked or special source payload is unsupported')
    files = {p.relative_to(release).as_posix(): p for p in entries if p.is_file()}
    if set(files) != set(before['files']) | EXTRA_FILES:
        raise ValueError('Source payload contains missing or unrecorded files')
    for name, digest in before['files'].items():
        checked_path(name)
        if sha(files[name]) != digest:
            raise ValueError('Source payload bytes differ from its observed inventory')
    if json.loads(files['distribution-inventory.json'].read_bytes()) != before:
        raise ValueError('Copied source inventory differs from independently observed source')
    for name in before['files'].keys() - after['files'].keys():
        files[name].unlink()
    for path in sorted((p for p in release.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(path.iterdir()):
            path.rmdir()
    files['distribution-inventory.json'].write_bytes(inventory_bytes(after))
    return {name: sha(release / name) for name in sorted(set(after['files']) | EXTRA_FILES)}


class Docker:
    def run(self, *args, timeout=120):
        completed = subprocess.run(['docker', *args], capture_output=True, timeout=timeout)
        if completed.returncode:
            raise RuntimeError('Docker command failed; no automatic retry: ' + args[0])
        return completed.stdout

    def inspect(self, kind, ref):
        result = subprocess.run(['docker', kind, 'inspect', ref], capture_output=True, timeout=30)
        if result.returncode:
            error = result.stderr.decode('utf8', 'replace').strip().lower()
            prefix = 'error response from daemon: '
            error = error.removeprefix(prefix).removeprefix('error: ')
            if error == 'no such ' + kind + ': ' + ref.lower():
                return None
            raise RuntimeError('Docker inspection unavailable; absence not proven')
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError('Malformed Docker inspection')
        return rows[0]


def build(root, *, image, record_path, packages, output, gate, plan_only=False, docker=None, observer=None):
    docker = docker or Docker()
    observer = observer or inspect_image
    if not IMAGE.fullmatch(image):
        raise ValueError('Immutable source image ID required')
    output = output.resolve()
    if (not output.is_relative_to(root / 'docs/evidence' / gate) or output.exists()
            or not re.fullmatch('[A-Za-z0-9_-]+', output.name)):
        raise ValueError('Fresh named evidence output under owning gate required')
    clean = _clean_inputs(root)
    base = observer(image)
    record = source_record(record_path, image, base, clean)
    mapping = None
    if set(packages) != base['inventory'].get('artifacts', {}).keys():
        mapping = {}
        def recorded_toml(name):
            checked_path(name)
            source = source_path(root, name)
            if (not source.is_file()
                    or sha(source) != record['source_sha256'].get(name)):
                raise ValueError('Historical partial-removal source manifest/recipe is unavailable or changed')
            return tomllib.loads(source.read_text(encoding='utf8'))
        for key in ('reference_packages', 'application_packages'):
            for name in base['inventory']['policy'].get(key, []):
                document = recorded_toml(name)
                if key == 'application_packages':
                    document = recorded_toml(document['manifest'])
                mapping[name] = document['plugin']['id']
    inventory, diff = subtract_inventory(base, packages, mapping)
    dockerfile = render_dockerfile(root, clean)
    provenance = dict(source_image=image, source_inventory_digest=base['inventory_digest'],
        source_build_record_sha256=sha(record_path), payload_source_commit=record['git_base'],
        payload_source_sha256=record['source_sha256'], removed_packages=list(packages),
        source_diff=diff, final_base=clean['python_image'], clean_inputs=clean,
        dependency_image_is_copy_input_only=True, source_payload_is_not_rebuilt_from_host=True)
    if plan_only:
        return dict(result='planned_not_built', remaining_addons=sorted(inventory['native_addons']),
            remaining_artifacts=sorted(inventory.get('artifacts', {})), **provenance)
    private = protect_directory(root / '.local/operator/builds')
    private_record = private / (output.name + '.json')
    work = private / (output.name + '-work')
    if private_record.exists() or work.exists():
        raise RuntimeError('Build already attempted; reconcile its existing record without replay')
    source_metadata = docker.inspect('image', image)
    if (source_metadata is None or source_metadata['Id'] != image
            or not source_metadata.get('RepoTags')):
        raise ValueError('Source image must retain its own immutable identity and tags')
    alias = 'modular-platform:removal-input-' + output.name.lower()
    name = 'mp-clean-removal-input-' + uuid4().hex
    for kind, ref in (('image', alias), ('container', name)):
        if docker.inspect(kind, ref) is not None:
            raise RuntimeError('Build input alias/container already exists')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    tag = 'modular-platform:stage-' + stamp
    inputs = ['tools/build_clean_removal.py', 'tools/build_candidate.py', 'tools/clean_image_audit.py',
        'tools/application_package.py',
        'deploy/Dockerfile', 'deploy/runtime.lock.json', 'deploy/requirements-r1.lock',
        *['packages/platform_sdk/modular_platform/' + name + '.py' for name in
            ('artifact_removal', 'deployment', 'contracts', 'operator_os', 'operator_store', 'plans')]]
    host_inputs = {p: sha(root / p) for p in inputs}
    intent = dict(state='building', build_mode='clean-subtraction', result='not_deployed',
        tag=tag, source_alias=alias, input_container_name=name, output=str(output.relative_to(root)),
        git_base=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
        source_sha256=host_inputs, **provenance)
    output.mkdir(parents=True)
    _write_new(private_record, intent)
    context = protect_directory(work / 'context')
    release = protect_directory(context / 'release')
    (context / 'Dockerfile').write_text(dockerfile, encoding='utf8', newline='\n')
    (context / '.dockerignore').write_text('*\n!Dockerfile\n!release\n!release/**\n', encoding='utf8')
    child = None
    aliased = False
    identity = None
    phase = 'copy_source'
    try:
        with ProcessLock(root / '.local/operator/control/locks', 'candidate-build'):
            if docker.inspect('image', alias) is not None or docker.inspect('container', name) is not None:
                raise RuntimeError('Input resource appeared before the exclusive build')
            child = docker.run('create', '--name', name, '--label', 'com.modular.build=' + output.name,
                '--network', 'none', '--read-only', '--entrypoint', '/bin/true', image).decode().strip()
            if not re.fullmatch('[0-9a-f]{64}', child):
                raise ValueError('Input container full identity unavailable; inspect before cleanup')
            _write_new(work / 'input-container.json', dict(id=child, name=name, image_id=image))
            docker.run('cp', child + ':/opt/modular/.', str(release))
            metadata = docker.inspect('container', child)
            if (metadata['Id'] != child or metadata['Image'] != image or metadata['State']['Running']
                    or metadata['Mounts'] or metadata['Config']['Labels'].get('com.modular.build') != output.name):
                raise ValueError('Input container identity changed; do not remove unknown resource')
            docker.run('rm', child)
            child = None
            expected_files = prepare_payload(release, base['inventory'], inventory)
            if (expected_files['requirements.lock'] != base['python_lock_digest'][7:]
                    or (release / 'startup-profile').read_bytes() != b'r1\n'):
                raise ValueError('Copied runtime lock or startup profile differs')
            _write_new(work / 'prepared.json', dict(expected_inventory=inventory,
                expected_files=expected_files, dockerfile_sha256=sha(context / 'Dockerfile')))
            phase = 'build'
            if docker.inspect('image', alias) is not None:
                raise RuntimeError('Dependency alias appeared; refuse to overwrite it')
            docker.run('tag', image, alias)
            aliased = True
            if docker.inspect('image', alias)['Id'] != image:
                raise ValueError('Dependency alias changed')
            command = ['docker', 'build', '--target', 'clean-subtraction', '--build-arg',
                'DEPENDENCY_IMAGE=' + alias, '--build-arg', 'PYTHON_IMAGE=' + clean['python_image'],
                '--build-arg', 'DEBIAN_SNAPSHOT=' + clean['debian_snapshot'], '-t', tag, str(context)]
            with (output / 'build.log').open('xb') as log:
                result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            if result.returncode:
                raise RuntimeError('Clean subtraction build failed; inspect retained log, do not retry blindly')
            identity = docker.inspect('image', tag)['Id']
            phase = 'verify'
            runtime = observer(identity)
            descriptor = dict(base_image_id=image, target_image_id=identity,
                inventory_digest=runtime['inventory_digest'], runtime_digest=data_digest(runtime))
            actual_diff = validate_removal_image(base, runtime, descriptor, packages)
            if runtime['inventory'] != inventory or actual_diff != diff:
                raise ValueError('Built subtraction differs from the exact planned inventory')
            rtl = _verify_clean_rtl(identity, root)
            from clean_image_audit import audit_image
            archive = work / 'image.tar'
            docker.run('image', 'save', '--output', str(archive), identity)
            audit = audit_image(archive, identity, docker.inspect('image', identity), expected_files,
                source_layers=source_metadata['RootFS']['Layers'])
            _write_new(output / 'image-audit.json', audit)
            if any(sha(root / p) != h for p, h in host_inputs.items()):
                raise ValueError('Host build inputs changed during build')
            phase = 'release_input_alias'
            metadata = docker.inspect('image', alias)
            if (metadata is None or metadata['Id'] != image
                    or set(metadata['RepoTags']) != set(source_metadata['RepoTags']) | {alias}):
                raise ValueError('Source tag identity drift; refuse automatic untagging')
            docker.run('image', 'rm', alias)
            aliased = False
            report = dict(intent, state='built', result='built_not_deployed', image_id=identity,
                inventory_digest=runtime['inventory_digest'], artifacts=inventory.get('artifacts', {}),
                deployment_changed=False, clean_verification=rtl,
                audit_sha256=sha(output / 'image-audit.json'), utc=datetime.now(timezone.utc).isoformat())
            _write_new(output / 'candidate-build.json', report)
            private_record.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
            return report
    except Exception as error:
        failure = dict(intent, state='failed', phase=phase, error_type=type(error).__name__,
            deployment_changed=False, input_container_id=child, image_id=identity)
        _write_new(output / 'candidate-failed.json', failure)
        private_record.write_text(json.dumps(failure, indent=2) + '\n', encoding='utf8')
        raise
    finally:
        # Never sweep containers after uncertain identity/copy failures. Its exact
        # durable ID remains for review. Only our verified dependency tag is freed.
        if aliased:
            metadata = docker.inspect('image', alias)
            if (metadata is None or metadata['Id'] != image
                    or set(metadata['RepoTags']) != set(source_metadata['RepoTags']) | {alias}):
                raise RuntimeError('Source tag identity drift; refuse automatic untagging')
            docker.run('image', 'rm', alias)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--source-build-record', required=True, type=Path)
    parser.add_argument('--remove-package', action='append', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--gate', choices=['G5', 'G6', 'G7'], default='G7')
    parser.add_argument('--plan', action='store_true', help='Inspect and derive only; no build/output/site changes')
    args = parser.parse_args()
    report = build(ROOT, image=args.image_id, record_path=args.source_build_record,
        packages=args.remove_package, output=args.output, gate=args.gate, plan_only=args.plan)
    keys = ['result', 'source_image', 'removed_packages', 'tag', 'image_id', 'inventory_digest']
    if args.plan:
        keys += ['source_diff', 'final_base', 'remaining_addons', 'remaining_artifacts']
    print(json.dumps({k: report[k] for k in keys if k in report}))


if __name__ == '__main__':
    main()
