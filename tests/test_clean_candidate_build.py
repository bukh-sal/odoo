"""Actual clean candidate CLI route with a fake Docker/subprocess boundary."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess as real_subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import build_candidate

POLICY='deploy/distribution-r1-core.json'


class FakeSubprocess:
    STDOUT=real_subprocess.STDOUT
    def __init__(self,root,returncode=0):
        self.root=root;self.commands=[];self.returncode=returncode
        self.lock=json.loads((ROOT/'deploy/stock-rtl/package-lock.json').read_text())
    def run(self,command,**kwargs):
        self.commands.append(('run',list(command)))
        code=1 if list(command)[:3]==['docker','image','inspect'] else self.returncode
        return types.SimpleNamespace(returncode=code,stdout=b'',stderr=b'')
    def check_output(self,command,**kwargs):
        command=list(command);self.commands.append(('check_output',command))
        if command[:3]==['git','rev-parse','HEAD']:return b'fixturehead\n'
        if command[:4]==['docker','run','--rm','--network']:
            entry=command[command.index('--entrypoint')+1]
            if entry.endswith('/node'):return getattr(self,'node_output',b'v24.22.2\n')
            if entry.endswith('/rtlcss'):return getattr(self,'rtl_output',b'rtlcss version: 4.3.0\n')
            if entry=='find' or entry.endswith('/find'):
                packages=[name for name in self.lock['packages'] if name]
                if getattr(self,'missing_notice',False):packages=packages[1:]
                return ('\n'.join('/opt/stock-rtl/'+name+'/LICENSE' for name in packages)+'\n').encode()
        if command[:3]==['docker','image','inspect']:
            target=command[3]
            if target.startswith('modular-platform:dependency-base-'):
                return (getattr(self,'dependency_base','sha256:'+'d'*64)+'\n').encode()
            return ('sha256:'+'d'*64+'\n').encode()
        raise AssertionError('unexpected check_output: '+repr(command))


class FakeEnvironment:
    def __init__(self,root):
        self.root=root;self.fake=FakeSubprocess(root)
        self.runtime=dict(inventory_digest='sha256:'+'e'*64,inventory={'artifacts':{}},
            modified_files=[],missing_addon_files=[],unexpected_addon_files=[])
    def __enter__(self):
        root=self.root
        (root/'deploy').mkdir(parents=True);(root/'deploy/stock-rtl').mkdir()
        (root/'deploy/runtime.lock.json').write_bytes((ROOT/'deploy/runtime.lock.json').read_bytes())
        (root/'deploy/Dockerfile').write_bytes((ROOT/'deploy/Dockerfile').read_bytes())
        (root/'deploy/requirements-r1.lock').write_bytes((ROOT/'deploy/requirements-r1.lock').read_bytes())
        for name in ('package.json','package-lock.json','rtlcss'):
            (root/'deploy/stock-rtl'/name).write_bytes((ROOT/'deploy/stock-rtl'/name).read_bytes())
        (root/POLICY).write_bytes((ROOT/POLICY).read_bytes())
        (root/'deploy/distribution-r1-appfree-probe.json').write_bytes((ROOT/'deploy/distribution-r1-appfree-probe.json').read_bytes())
        (root/'docs/evidence/G5').mkdir(parents=True)
        return self
    def __exit__(self,*args):return False


def invoke(environment,extra=(),*,real_operator=False):
    argv=['build_candidate.py','--output',str(environment.root/'docs/evidence/G5/clean-01'),'--gate','G5',*extra]
    output=io.StringIO()
    protect=build_candidate.protect_directory if real_operator else lambda path:(Path(path).mkdir(parents=True,exist_ok=True),Path(path))[1]
    lock=build_candidate.ProcessLock if real_operator else lambda *args,**kwargs:contextlib.nullcontext()
    with patch.object(build_candidate,'ROOT',environment.root),\
         patch.object(build_candidate,'subprocess',environment.fake),\
         patch.object(build_candidate,'source_input_paths',lambda root,policy:['deploy/Dockerfile']),\
         patch.object(build_candidate,'inspect_image',lambda image_id:environment.runtime),\
         patch.object(build_candidate,'protect_directory',protect),\
         patch.object(build_candidate,'ProcessLock',lock),\
         patch.object(sys,'argv',argv),contextlib.redirect_stdout(output):
        build_candidate.main()
    return output.getvalue(),environment.fake


class CleanCandidateBuild(unittest.TestCase):
    def test_fresh_checkout_creates_private_control_and_holds_real_os_lock_before_docker(self):
        from modular_platform.operator_os import ProcessLock,OperatorError,verify_private_directory
        with tempfile.TemporaryDirectory(prefix='mp-builder-real-lock-') as temporary,FakeEnvironment(Path(temporary)) as environment:
            control=environment.root/'.local/operator/control';original=environment.fake.run
            self.assertFalse(control.exists());seen=[]
            def run(command,*args,**kwargs):
                if command[:2]==['docker','build']:
                    verify_private_directory(control);verify_private_directory(control/'locks')
                    with self.assertRaises(OperatorError):
                        with ProcessLock(control/'locks','candidate-build'):self.fail('Build lock was not held')
                    seen.append('locked')
                return original(command,*args,**kwargs)
            with patch.object(environment.fake,'run',side_effect=run):invoke(environment,real_operator=True)
            self.assertEqual(seen,['locked'])
            with ProcessLock(control/'locks','candidate-build'):pass
            self.assertFalse((control/'policy.json').exists());self.assertFalse((control/'operations.sqlite3').exists())

    def test_existing_unsafe_control_refuses_before_docker_without_repair(self):
        from modular_platform import operator_os
        with tempfile.TemporaryDirectory(prefix='mp-builder-unsafe-lock-') as temporary,FakeEnvironment(Path(temporary)) as environment:
            control=environment.root/'.local/operator/control';control.mkdir(parents=True)
            (control/'marker').write_bytes(b'preserve existing control')
            if os.name!='nt':control.chmod(0o755)
            before=operator_os._windows_acl(control) if os.name=='nt' else control.stat().st_mode
            with self.assertRaises(operator_os.OperatorError):invoke(environment,real_operator=True)
            after=operator_os._windows_acl(control) if os.name=='nt' else control.stat().st_mode
            self.assertEqual(before,after);self.assertEqual((control/'marker').read_bytes(),b'preserve existing control')
            self.assertFalse(any(command[0]=='docker' for _,command in environment.fake.commands))

    def test_dockerfile_clean_target_ancestry_and_legacy_default_are_source_checked(self):
        source=(ROOT/'deploy/Dockerfile').read_text(encoding='utf8')
        self.assertIn('FROM ${RTL_NODE_IMAGE} AS rtl-compiler',source)
        self.assertIn('FROM ${PYTHON_IMAGE} AS clean-runtime',source)
        self.assertIn('COPY --from=builder /venv /venv',source)
        self.assertIn('COPY --from=builder /release /opt/modular',source)
        self.assertIn('COPY --from=rtl-compiler /opt/stock-rtl /opt/stock-rtl',source)
        clean=source[source.index('AS clean-runtime'):source.index('FROM ${PYTHON_IMAGE} AS runtime')]
        self.assertNotIn('COPY tools /opt/modular/tools',clean)
        self.assertNotIn('COPY tests/fixtures',clean)
        self.assertNotIn('AS builder',clean)
        self.assertNotIn('ENV CC=',clean)
        self.assertNotIn('modular-native-cc',clean)
        runtime=source[source.index('FROM ${PYTHON_IMAGE} AS runtime'):]
        self.assertIn('COPY tools /opt/modular/tools',runtime)
        self.assertIn('COPY tests/fixtures/addons /opt/modular/fixtures',runtime)
        self.assertGreater(source.index('FROM ${PYTHON_IMAGE} AS runtime'),source.index('FROM ${PYTHON_IMAGE} AS clean-runtime'))

    def test_compiler_frontend_is_bound_by_actual_curated_source_inputs(self):
        from build_inputs import source_input_paths
        self.assertIn('deploy/reproducible_cc.py',source_input_paths(ROOT,POLICY))

    def test_clean_cli_targets_clean_runtime_and_records_pins(self):
        with tempfile.TemporaryDirectory(prefix='mp-clean-build-') as temporary, FakeEnvironment(Path(temporary)) as environment:
            output,fake=invoke(environment)
            self.assertIn('built_not_deployed',output)
            build=[command for kind,command in fake.commands if kind=='run'][0]
            self.assertEqual(build[:3],['docker','build','-f'])
            self.assertIn('--target',build);self.assertEqual(build[build.index('--target')+1],'clean-runtime')
            self.assertIn('RTL_NODE_IMAGE='+build_candidate.CLEAN_NODE_IMAGE,build)
            self.assertNotIn('deploy/Dockerfile.core-maintenance',build)
            self.assertFalse(any('DEPENDENCY_BASE_IMAGE' in arg for arg in build))
            report=json.loads((environment.root/'docs/evidence/G5/clean-01/candidate-build.json').read_text())
            self.assertEqual(report['state'],'built');self.assertEqual(report['build_mode'],'clean')
            self.assertEqual(report['docker_target'],'clean-runtime')
            self.assertEqual(report['rtl_node_image'],build_candidate.CLEAN_NODE_IMAGE)
            lock=json.loads((ROOT/'deploy/runtime.lock.json').read_bytes())
            self.assertEqual(report['python_image'],lock['python_image'])
            self.assertIn('PYTHON_IMAGE='+lock['python_image'],build)
            self.assertEqual(report['debian_snapshot'],lock['debian_snapshot'])
            self.assertEqual(report['clean_verification']['node_version'],'v24.22.2')
            self.assertTrue(report['source_sha256'])
            self.assertEqual(report['build_cache_policy'],'normal_cache')
            self.assertNotIn('--no-cache-filter',build)

    def test_clean_native_recompile_uses_only_fixed_builder_filter_and_records_mode(self):
        with tempfile.TemporaryDirectory(prefix='mp-recompile-build-') as temporary,FakeEnvironment(Path(temporary)) as environment:
            _,fake=invoke(environment,('--recompile-dependencies',))
            build=[command for kind,command in fake.commands if kind=='run'][0]
            self.assertEqual(build[:4],['docker','build','--no-cache-filter','builder'])
            self.assertEqual(build.count('--no-cache-filter'),1)
            self.assertNotIn('--no-cache',build);self.assertNotIn('--network=none',build)
            self.assertFalse(any('prune' in command for _,command in fake.commands))
            report=json.loads((environment.root/'docs/evidence/G5/clean-01/candidate-build.json').read_bytes())
            self.assertEqual(report['build_cache_policy'],'recompile_builder_stage')
            self.assertEqual(report['command'],build)

    def test_native_recompile_incompatible_modes_refuse_before_output_or_docker(self):
        for extra in (('--recompile-dependencies','--policy','deploy/distribution-r1-appfree-probe.json'),
                ('--recompile-dependencies','--reproduction'),
                ('--recompile-dependencies','--dependency-base-image','sha256:'+'a'*64)):
            with tempfile.TemporaryDirectory(prefix='mp-recompile-refuse-') as temporary,FakeEnvironment(Path(temporary)) as environment:
                with self.assertRaises(ValueError):invoke(environment,extra)
                self.assertEqual(environment.fake.commands,[])
                self.assertFalse((environment.root/'docs/evidence/G5/clean-01').exists())

    def test_clean_rejects_dependency_base_and_reproduction_before_output(self):
        for extra in (('--reproduction',),('--dependency-base-image','sha256:'+'a'*64),('--reproduction','--dependency-base-image','sha256:'+'a'*64)):
            with tempfile.TemporaryDirectory(prefix='mp-clean-reject-') as temporary, FakeEnvironment(Path(temporary)) as environment:
                with self.assertRaisesRegex(ValueError,'Clean runtime rejects'):
                    invoke(environment,extra)
                self.assertFalse((environment.root/'docs/evidence/G5/clean-01').exists())
                self.assertEqual(environment.fake.commands,[])

    def test_maintenance_dependency_base_route_remains_on_core_maintenance_dockerfile(self):
        with tempfile.TemporaryDirectory(prefix='mp-maint-build-') as temporary, FakeEnvironment(Path(temporary)) as environment:
            base_id='sha256:'+'a'*64;environment.fake.dependency_base=base_id
            runtime=dict(inventory_digest='sha256:'+'e'*64,inventory={'artifacts':{}},
                python='3.12.16',architecture='amd64',markers={},python_metadata=[],
                python_lock_digest='sha256:'+hashlib.sha256((ROOT/'deploy/requirements-r1.lock').read_bytes()).hexdigest(),modified_files=False,missing_addon_files=False,unexpected_addon_files=False)
            seen=[]
            def inspect(image_id):
                seen.append(image_id)
                return runtime
            argv=['build_candidate.py','--output',str(environment.root/'docs/evidence/G5/maint-01'),'--gate','G5',
                  '--policy','deploy/distribution-r1-appfree-probe.json','--dependency-base-image',base_id]
            with patch.object(build_candidate,'ROOT',environment.root),\
                 patch.object(build_candidate,'subprocess',environment.fake),\
                 patch.object(build_candidate,'source_input_paths',lambda root,policy:['deploy/Dockerfile']),\
                 patch.object(build_candidate,'inspect_image',side_effect=inspect),\
                 patch.object(build_candidate,'protect_directory',lambda path:(Path(path).mkdir(parents=True,exist_ok=True),Path(path))[1]),\
                 patch.object(build_candidate,'ProcessLock',lambda *args,**kwargs:contextlib.nullcontext()),\
                 patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
                build_candidate.main()
            commands=[cmd for kind,cmd in environment.fake.commands if kind=='run']
            build=[cmd for cmd in commands if cmd[:2]==['docker','build']][0]
            self.assertIn('deploy/Dockerfile.core-maintenance',build)
            self.assertTrue(any(arg.startswith('DEPENDENCY_BASE_IMAGE=') for arg in build))
            self.assertNotIn('--target',build)
            self.assertNotIn('RTL_NODE_IMAGE=',build)
            report=json.loads((environment.root/'docs/evidence/G5/maint-01/candidate-build.json').read_text())
            self.assertNotIn('build_mode',report)

    def test_invalid_surface_or_sdk_free_clean_policy_refuses_before_docker(self):
        for field,value in (('runtime_surface','cleen'),('platform_sdk',False),('platform_sdk',1)):
            with tempfile.TemporaryDirectory(prefix='mp-clean-policy-') as temporary,FakeEnvironment(Path(temporary)) as environment:
                path=environment.root/POLICY;policy=json.loads(path.read_bytes());policy[field]=value
                path.write_text(json.dumps(policy),encoding='utf8')
                with self.assertRaises(ValueError):invoke(environment)
                self.assertEqual(environment.fake.commands,[])
                self.assertFalse((environment.root/'docs/evidence/G5/clean-01').exists())

    def test_clean_input_pin_or_stage_mismatch_refuses_before_docker(self):
        for before,after in (('ARG PYTHON_IMAGE=','ARG WRONG_PYTHON_IMAGE='),
                             ('FROM ${PYTHON_IMAGE} AS clean-runtime','FROM builder AS clean-runtime')):
            with tempfile.TemporaryDirectory(prefix='mp-clean-stage-') as temporary,FakeEnvironment(Path(temporary)) as environment:
                path=environment.root/'deploy/Dockerfile';source=path.read_text(encoding='utf8')
                path.write_text(source.replace(before,after),encoding='utf8')
                with self.assertRaisesRegex(ValueError,'Clean Dockerfile'):invoke(environment)
                self.assertEqual(environment.fake.commands,[])
                self.assertFalse((environment.root/'docs/evidence/G5/clean-01').exists())

    def test_bad_compiler_or_notice_closure_preserves_image_failure_evidence(self):
        for field,value in (('node_output',b'v24.0.0\n'),('rtl_output',b'rtlcss version: 4.2.0\n'),('missing_notice',True)):
            with tempfile.TemporaryDirectory(prefix='mp-clean-verify-') as temporary,FakeEnvironment(Path(temporary)) as environment:
                setattr(environment.fake,field,value)
                with self.assertRaises(RuntimeError):invoke(environment)
                output=environment.root/'docs/evidence/G5/clean-01'
                failure=json.loads((output/'candidate-verification-failed.json').read_bytes())
                self.assertEqual(failure['state'],'verification_failed')
                self.assertEqual(failure['phase'],'clean_postbuild_verification')
                self.assertEqual(failure['image_id'],'sha256:'+'d'*64)
                self.assertFalse(failure['deployment_changed'])
                self.assertEqual(json.loads((environment.root/'.local/operator/builds/clean-01.json').read_bytes()),failure)
                self.assertFalse((output/'candidate-build.json').exists())

    def test_inspected_inventory_drift_is_retained_as_verification_failure(self):
        for field in ('modified_files','missing_addon_files','unexpected_addon_files'):
            with tempfile.TemporaryDirectory(prefix='mp-clean-drift-') as temporary,FakeEnvironment(Path(temporary)) as environment:
                environment.runtime[field]=['unexpected-source']
                with self.assertRaisesRegex(RuntimeError,'runtime inventory'):invoke(environment)
                output=environment.root/'docs/evidence/G5/clean-01'
                failure=json.loads((output/'candidate-verification-failed.json').read_bytes())
                self.assertEqual(failure['state'],'verification_failed')
                self.assertEqual(failure['image_id'],'sha256:'+'d'*64)
                self.assertFalse((output/'candidate-build.json').exists())

    def test_clean_build_failure_retains_record_and_no_candidate(self):
        with tempfile.TemporaryDirectory(prefix='mp-clean-fail-') as temporary, FakeEnvironment(Path(temporary)) as environment:
            environment.fake.returncode=1
            with self.assertRaisesRegex(RuntimeError,'Candidate build failed'):
                invoke(environment)
            output=environment.root/'docs/evidence/G5/clean-01'
            self.assertTrue((output/'build.log').exists())
            record=environment.root/'.local/operator/builds/clean-01.json'
            self.assertTrue(record.exists())
            self.assertEqual(json.loads(record.read_text())['state'],'building')
            self.assertFalse((output/'candidate-build.json').exists())

    def test_forced_native_build_failure_retains_explicit_cache_policy(self):
        with tempfile.TemporaryDirectory(prefix='mp-recompile-fail-') as temporary,FakeEnvironment(Path(temporary)) as environment:
            environment.fake.returncode=1
            with self.assertRaisesRegex(RuntimeError,'Candidate build failed'):invoke(environment,('--recompile-dependencies',))
            record=json.loads((environment.root/'.local/operator/builds/clean-01.json').read_bytes())
            self.assertEqual(record['state'],'building');self.assertEqual(record['build_cache_policy'],'recompile_builder_stage')
            self.assertEqual(record['command'][2:4],['--no-cache-filter','builder'])
            self.assertFalse((environment.root/'docs/evidence/G5/clean-01/candidate-build.json').exists())


if __name__=='__main__':
    unittest.main()
