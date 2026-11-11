"""Exercise the real builder ordering and guards with fake external Docker I/O."""
import contextlib
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'packages/platform_sdk')]
import build_clean_removal as builder

SOURCE = 'sha256:' + 'a' * 64
TARGET = 'sha256:' + 'b' * 64
PLUGIN = 'org.example.alpha'


def fixture(two=False):
    contents = {'addons/base/__manifest__.py': b'base',
        'tools/start_worker.py': b'guarded entrypoint',
        'addons/mp_alpha/__manifest__.py': b'alpha',
        'artifacts/org.example.alpha-1.0.0.mplug': b'alpha archive'}
    addons = dict(base=dict(depends=[]), mp_alpha=dict(depends=['base']))
    artifact = dict(plugin_id=PLUGIN, addon='mp_alpha', file='org.example.alpha-1.0.0.mplug',
        version='1.0.0', digest='sha256:' + hashlib.sha256(b'alpha archive').hexdigest())
    artifacts = {PLUGIN: artifact}
    paths = ['plugins/alpha/plugin.toml']
    if two:
        contents.update({'addons/mp_beta/__manifest__.py': b'beta',
            'artifacts/org.example.beta-1.0.0.mplug': b'beta archive'})
        addons['mp_beta'] = dict(depends=['base'])
        artifacts['org.example.beta'] = dict(artifact, plugin_id='org.example.beta',
            addon='mp_beta', file='org.example.beta-1.0.0.mplug')
        paths.append('plugins/beta/plugin.toml')
    inventory = dict(policy=dict(runtime_surface='clean', platform_sdk=True, stock_webclient=True,
        addons=list(addons), explicit_install=list(addons), server_wide_modules=['base'],
        reference_packages=paths, profile='Retained original composition provenance'),
        files={p: hashlib.sha256(v).hexdigest() for p, v in contents.items()},
        artifacts=artifacts, native_addons=addons, reference_composition=dict(
            models={'alpha.model': PLUGIN}, fields={}, ui_contributions=[PLUGIN + ':edit']))
    runtime = dict(inventory=inventory, native_manifests={a: dict(v, version='19.0.1.0.0') for a, v in addons.items()},
        inventory_digest='sha256:' + hashlib.sha256(builder.inventory_bytes(inventory)).hexdigest(),
        python='3.12.16', architecture='amd64', markers={}, accepted_wheel_tags=['exact'],
        python_metadata=[dict(name='native-dependency', version='1.0', digest='native-binary-hash')],
        python_lock_digest='sha256:' + hashlib.sha256((ROOT / 'deploy/requirements-r1.lock').read_bytes()).hexdigest(),
        published_release_protocol=1, modified_files=[], missing_addon_files=[], unexpected_addon_files=[])
    return runtime, contents


class FakeDocker:
    def __init__(self, base, contents):
        self.base = base
        self.contents = contents
        self.images = {SOURCE: dict(Id=SOURCE, RepoTags=['modular-platform:source'], RootFS=dict(Layers=['source']))}
        self.commands = []
        self.child = None

    def inspect(self, kind, ref):
        self.commands.append(('inspect', kind, ref))
        if kind == 'image':
            return copy.deepcopy(self.images.get(ref))
        return copy.deepcopy(self.child) if self.child and ref in (self.child['Id'], self.child['Name']) else None

    def run(self, *args, **kwargs):
        self.commands.append(tuple(args))
        if args[0] == 'create':
            self.child = dict(Id='c' * 64, Name=args[args.index('--name') + 1], Image=SOURCE,
                State=dict(Running=False), Mounts=[], Config=dict(Labels={
                    'com.modular.build': args[args.index('--label') + 1].split('=', 1)[1]}))
            return (self.child['Id'] + '\n').encode()
        if args[0] == 'cp':
            release = Path(args[2])
            for name, data in self.contents.items():
                path = release / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (release / 'distribution-inventory.json').write_bytes(builder.inventory_bytes(self.base['inventory']))
            (release / 'requirements.lock').write_bytes((ROOT / 'deploy/requirements-r1.lock').read_bytes())
            (release / 'startup-profile').write_bytes(b'r1\n')
        elif args[0] == 'rm':
            self.child = None
        elif args[0] == 'tag':
            self.images[SOURCE]['RepoTags'].append(args[2])
            self.images[args[2]] = self.images[SOURCE]
        elif args[:2] == ('image', 'rm'):
            alias = args[2]
            self.images[SOURCE]['RepoTags'].remove(alias)
            self.images.pop(alias)
        elif args[:2] == ('image', 'save'):
            Path(args[args.index('--output') + 1]).write_bytes(b'audited export fixture')
        else:
            raise AssertionError('Unexpected Docker call ' + repr(args))
        return b''


class Environment:
    def __init__(self, root):
        self.root = root
        self.base, self.contents = fixture()
        self.docker = FakeDocker(self.base, self.contents)
        self.output = root / 'docs/evidence/G7/remove-01'
        for name in ('deploy/Dockerfile', 'deploy/runtime.lock.json', 'deploy/requirements-r1.lock',
                'deploy/stock-rtl/package-lock.json', 'deploy/stock-rtl/package.json', 'deploy/stock-rtl/rtlcss',
                'tools/build_clean_removal.py', 'tools/clean_image_audit.py', 'tools/build_candidate.py',
                *['packages/platform_sdk/modular_platform/' + name + '.py' for name in
                    ('artifact_removal', 'deployment', 'contracts', 'operator_os', 'operator_store', 'plans')]):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        self.record = builder._clean_inputs(root) | dict(state='built', result='built_not_deployed',
            image_id=SOURCE, inventory_digest=self.base['inventory_digest'], artifacts=self.base['inventory']['artifacts'],
            source_sha256={'old-source.py': 'd' * 64}, git_base='historical-payload-commit')
        self.record_path = root / 'source-build.json'
        self.save_record()
        inv, _ = builder.subtract_inventory(self.base, [PLUGIN])
        self.after = copy.deepcopy(self.base)
        self.after['inventory'] = inv
        self.after['native_manifests'].pop('mp_alpha')
        self.after['inventory_digest'] = 'sha256:' + hashlib.sha256(builder.inventory_bytes(inv)).hexdigest()
        self.builds = 0
        self.fail_build = False
        self.fail_audit = False
        self.fail_verify = False

    def save_record(self):
        self.record_path.write_text(json.dumps(self.record), encoding='utf8')

    def subprocess_run(self, command, **kwargs):
        if command[:2] != ['docker', 'build']:
            raise AssertionError(command)
        self.builds += 1
        tag = command[command.index('-t') + 1]
        self.docker.images[tag] = dict(Id=TARGET, RepoTags=[tag], RootFS=dict(Layers=['pinned', 'clean']))
        kwargs['stdout'].write(b'build fixture\n')
        return SimpleNamespace(returncode=int(self.fail_build))

    def observe(self, image):
        result = copy.deepcopy(self.base if image == SOURCE else self.after)
        if image == TARGET and self.fail_verify:
            result['python_metadata'][0]['digest'] = 'changed native binary'
        return result

    def audit(self, *args, **kwargs):
        if self.fail_audit:
            raise ValueError('Old app in lower layer')
        return dict(result='fake export boundary; audited separately', image_id=TARGET)

    def invoke(self, plan=False):
        import clean_image_audit
        with patch.object(builder, 'protect_directory', side_effect=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[1]), \
                patch.object(builder, 'ProcessLock', return_value=contextlib.nullcontext()), \
                patch.object(builder.subprocess, 'run', side_effect=self.subprocess_run), \
                patch.object(builder.subprocess, 'check_output', return_value=b'current-host-commit\n'), \
                patch.object(builder, '_verify_clean_rtl', return_value=dict(node_version='v24.22.2')), \
                patch.object(clean_image_audit, 'audit_image', side_effect=self.audit):
            return builder.build(self.root, image=SOURCE, record_path=self.record_path,
                packages=[PLUGIN], output=self.output, gate='G7', plan_only=plan,
                docker=self.docker, observer=self.observe)


class CleanRemovalBuild(unittest.TestCase):
    def test_real_subtraction_uses_existing_guard_and_preserves_every_survivor(self):
        base, _ = fixture(True)
        before = copy.deepcopy(base)
        result, diff = builder.subtract_inventory(base, [PLUGIN], {
            'plugins/alpha/plugin.toml': PLUGIN, 'plugins/beta/plugin.toml': 'org.example.beta'})
        self.assertEqual(base, before)
        self.assertEqual(result['policy']['reference_packages'], ['plugins/beta/plugin.toml'])
        self.assertEqual(result['artifacts']['org.example.beta'], base['inventory']['artifacts']['org.example.beta'])
        self.assertEqual(len(diff), 2)
        self.assertTrue(all(row['target_sha256'] is None for row in diff))
        self.assertEqual(result['reference_composition'], dict(models={}, fields={}, ui_contributions=[]))

    def test_unknown_duplicate_framework_and_required_addon_removals_refuse(self):
        base, _ = fixture()
        for packages in ([], ['missing'], [PLUGIN, PLUGIN]):
            with self.assertRaises(ValueError):
                builder.subtract_inventory(base, packages)
        base['inventory']['native_addons']['base']['depends'] = ['mp_alpha']
        with self.assertRaisesRegex(Exception, 'still requires'):
            builder.subtract_inventory(base, [PLUGIN])

    def test_partial_removal_does_not_guess_source_mapping(self):
        base, _ = fixture(True)
        with self.assertRaisesRegex(ValueError, 'identity map'):
            builder.subtract_inventory(base, [PLUGIN])

    def test_plan_has_no_output_or_mutating_docker_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = Environment(Path(temporary))
            result = env.invoke(plan=True)
            self.assertEqual(result['result'], 'planned_not_built')
            self.assertFalse(env.output.exists())
            self.assertFalse((env.root / '.local').exists())
            self.assertEqual(env.docker.commands, [])

    def test_real_build_control_flow_binds_old_payload_and_new_host_then_releases_only_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = Environment(Path(temporary))
            report = env.invoke()
            self.assertEqual(report['state'], 'built')
            self.assertEqual(report['payload_source_commit'], 'historical-payload-commit')
            self.assertEqual(report['git_base'], 'current-host-commit')
            self.assertFalse(report['deployment_changed'])
            self.assertEqual(env.docker.images[SOURCE]['RepoTags'], ['modular-platform:source'])
            self.assertIsNone(env.docker.child)
            self.assertEqual(env.builds, 1)
            self.assertEqual(json.loads((env.output / 'candidate-build.json').read_bytes()), report)
            with self.assertRaisesRegex(ValueError, 'Fresh named'):
                env.invoke()
            self.assertEqual(env.builds, 1)

    def test_failed_build_runtime_drift_and_layer_leak_retain_failure_without_public_built_record(self):
        for flag in ('fail_build', 'fail_verify', 'fail_audit'):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temporary:
                env = Environment(Path(temporary))
                setattr(env, flag, True)
                with self.assertRaises(Exception):
                    env.invoke()
                failure = json.loads((env.output / 'candidate-failed.json').read_bytes())
                self.assertEqual(failure['state'], 'failed')
                self.assertFalse((env.output / 'candidate-build.json').exists())
                self.assertEqual(env.docker.images[SOURCE]['RepoTags'], ['modular-platform:source'])
                self.assertEqual(env.builds, 1)

    def test_source_record_pin_inventory_or_legacy_mode_drift_refuses_before_mutation(self):
        for key, value in (('image_id', TARGET), ('inventory_digest', 'bad'),
                ('debian_snapshot', 'different'), ('dockerfile_sha256', 'different'),
                ('build_mode', 'maintenance'), ('source_sha256', {})):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                env = Environment(Path(temporary))
                env.record[key] = value
                env.save_record()
                with self.assertRaises(ValueError):
                    env.invoke()
                self.assertFalse(env.output.exists())
                self.assertEqual(env.docker.commands, [])

    def test_alias_appearing_before_tag_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = Environment(Path(temporary))
            original = env.docker.inspect
            checks = []
            def inspect(kind, ref):
                if kind == 'image' and ':removal-input-' in ref:
                    checks.append(ref)
                    if len(checks) == 3:
                        return dict(Id='sha256:' + 'f' * 64, RepoTags=[ref])
                return original(kind, ref)
            env.docker.inspect = inspect
            with self.assertRaisesRegex(RuntimeError, 'refuse to overwrite'):
                env.invoke()
            self.assertFalse(any(c[0] == 'tag' for c in env.docker.commands))
            self.assertEqual(env.builds, 0)

    def test_late_source_tag_drift_retains_input_alias_for_review_and_never_publishes_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = Environment(Path(temporary))
            original = env.subprocess_run
            def build(command, **kwargs):
                result = original(command, **kwargs)
                env.docker.images[SOURCE]['RepoTags'].append('foreign-repository:keep')
                return result
            env.subprocess_run = build
            with self.assertRaisesRegex(RuntimeError, 'refuse automatic untagging'):
                env.invoke()
            self.assertFalse((env.output / 'candidate-build.json').exists())
            failure = json.loads((env.output / 'candidate-failed.json').read_bytes())
            self.assertEqual(failure['phase'], 'release_input_alias')
            self.assertEqual(failure['image_id'], TARGET)
            self.assertIn('foreign-repository:keep', env.docker.images[SOURCE]['RepoTags'])
            self.assertFalse(any(c[:2] == ('image', 'rm') for c in env.docker.commands))

    def test_unrecorded_or_modified_copied_source_never_builds(self):
        for path in ('unrecorded.py', 'addons/base/__manifest__.py'):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temporary:
                env = Environment(Path(temporary))
                env.contents[path] = b'bad copied bytes'
                with self.assertRaisesRegex(ValueError, 'payload'):
                    env.invoke()
                self.assertEqual(env.builds, 0)

    def test_clean_recipe_starts_from_pinned_base_and_never_copies_full_input_tree(self):
        text = builder.render_dockerfile(ROOT, builder._clean_inputs(ROOT))
        final = text.split('AS clean-subtraction\n')[1]
        self.assertNotIn('FROM ', final)
        self.assertNotIn('COPY --from=dependency-input /opt/modular', final)
        self.assertNotIn('rm -rf /opt/modular', final)
        self.assertIn('COPY release /opt/modular', final)
        self.assertIn('COPY --from=dependency-input /venv /venv', final)


if __name__ == '__main__':
    unittest.main()
