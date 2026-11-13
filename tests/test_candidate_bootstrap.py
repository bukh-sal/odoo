"""Actual public phase flow and file guards; Docker/kit/native boundaries are fake."""
import copy
import contextlib
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
import initialize_candidate as entry
from test_release_staging import staged_runtime


class CandidateBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs={p:entry.digest(ROOT/p) for p in entry.source_input_paths(ROOT,'deploy/distribution-r1-core.json')}

    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='mp-candidate-bootstrap-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.work=self.root/'fresh-site';self.record=self.root/'candidate-build.json'
        self.data=dict(state='built',result='built_not_deployed',deployment_changed=False,artifacts={},image_id='sha256:'+'a'*64,
            inventory_digest='sha256:'+'d'*64,git_base='1'*40,distribution_policy='deploy/distribution-r1-core.json',source_sha256=self.inputs)
        self.record.write_text(json.dumps(self.data),encoding='utf-8')
        self.base=['--workdir',str(self.work),'--build-record',str(self.record),'--port','18990','--runtime-subnet','10.205.11.16/28','--edge-subnet','10.205.11.32/28']
        self.runtime=staged_runtime([]);self.runtime['platform_version']='0.2.3';self.runtime['native_manifests']={'mp_core':dict(version='19.0.0.2.3')}
        self.runtime['inventory']['native_addons']=dict.fromkeys(entry.ADDONS)
        self.events=[]

    def run_cli(self,args):
        with contextlib.redirect_stdout(io.StringIO()):return entry.main(args)

    def protect(self,path):
        path=Path(path).absolute();self.assertTrue(path.is_relative_to(self.root))
        path.mkdir(parents=True,exist_ok=True);return path

    def write_state(self,site,phase):
        self.protect(site.local/'operator')
        state=dict(phase=phase,project='mp-r0-r1release012345abcdef',database='mp_disposable_r0_r1_release_012345abcdef',bootstrap_id='00000000-0000-4000-8000-000000000001',site_id='fixture-site',deployment_id='fixture-deployment',image_id=self.data['image_id'],inventory_digest=self.data['inventory_digest'],port=18990,url='http://release-012345abcdef.localhost:18990')
        entry.write(site.local/'state.json',state);return state

    def fake_prepare(self,site,images,source,trust,**kwargs):
        self.events.append(('prepare',images,kwargs));self.write_state(site,'configured')
        (site.local/'operator/trust.json').write_bytes(trust)

    def fake_initialize(self,site,state,addons):
        self.events.append(('initialize',addons));state['phase']='core-provision';entry.write(site.local/'state.json',state)
        entry.write(site.local/'fixtures.json',dict(site_id=state['site_id'],installed_plugins=[],workspaces=dict(A={},B={}),users=dict(operator={},alice={},bob={},worker={})))

    def fake_publish(self,site,state):
        self.events.append(('publish',));state['phase']='core_only_ready';entry.write(site.local/'state.json',state)
        entry.write(site.local/'operator/target.json',dict(worker_id='b'*64,image_id=self.data['image_id'],deployment_id=state['deployment_id'],sites=[dict(site_id=state['site_id'],database=state['database'])]))

    def fake_sql(self,*args,**kwargs):return json.dumps(dict(modules=sorted(entry.ADDONS),installations=0,features=0,grants=0,bindings=0)).encode()

    @contextlib.contextmanager
    def external_boundaries(self):
        with patch.object(entry,'protect_directory',side_effect=self.protect),patch.object(entry,'verify_private_directory'),patch.object(entry,'inspect_image',return_value=self.runtime),patch.object(entry,'Catalog') as catalog,patch.object(entry,'configuration'),patch.object(entry.Reference,'prepare_resources',autospec=True,side_effect=self.fake_prepare),patch.object(entry.Reference,'initialize_core',autospec=True,side_effect=self.fake_initialize),patch.object(entry.Reference,'publish',autospec=True,side_effect=self.fake_publish),patch.object(entry.Reference,'sql',autospec=True,side_effect=self.fake_sql):
            catalog.return_value.snapshot.return_value=[]
            yield

    def test_default_plan_and_unapproved_execution_have_no_process_or_directory_mutation(self):
        with patch.object(entry.subprocess,'run',side_effect=AssertionError('No processes in plan')),patch.object(entry.subprocess,'check_output',side_effect=AssertionError('No Docker in plan')),patch.object(entry,'protect_directory',side_effect=AssertionError('No directory writes')):
            result=self.run_cli(self.base);self.assertEqual(result['action'],'plan_only');self.assertFalse(result['allow_noninteractive_operations'])
            with self.assertRaisesRegex(ValueError,'disposable-development-site'):self.run_cli(['prepare',*self.base])
        self.assertFalse(self.work.exists())

    def test_real_phase_protocol_exact_inputs_interactive_default_and_fresh_worker(self):
        with self.external_boundaries():
            self.run_cli(['prepare',*self.base,'--disposable-development-site'])
            self.run_cli(['initialize','--workdir',str(self.work),'--disposable-development-site'])
            self.run_cli(['publish','--workdir',str(self.work),'--disposable-development-site'])
            status=self.run_cli(['status','--workdir',str(self.work)])
            self.assertEqual(status['phase'],'core_only_ready');self.assertEqual(status['completed'],['initialize','prepare','publish'])
            with self.assertRaises(ValueError):self.run_cli(['publish','--workdir',str(self.work),'--disposable-development-site'])
        self.assertEqual([r[0] for r in self.events],['prepare','initialize','publish'])
        self.assertEqual(self.events[0][1],entry.image_inputs(self.data));self.assertFalse(self.events[0][2]['allow_noninteractive'])
        self.assertEqual(self.events[1][1],'web,auth_password_policy,mp_core')
        self.assertEqual(json.loads((self.work/'private/site/operator/target.json').read_bytes())['worker_id'],'b'*64)

    def test_noninteractive_policy_requires_explicit_prepare_option_legacy_default_stays(self):
        self.assertIs(inspect.signature(entry.Reference.prepare_resources).parameters['allow_noninteractive'].default,True)
        with self.external_boundaries():self.run_cli(['prepare',*self.base,'--disposable-development-site','--allow-noninteractive-operations'])
        self.assertTrue(self.events[0][2]['allow_noninteractive'])

    def test_failed_or_app_record_and_changed_missing_source_refuse_before_workdir(self):
        variants=[dict(state='building'),dict(artifacts={'dev.local.extra':{}}),dict(image_id='tag:mutable'),dict(source_sha256=dict(self.inputs)|{next(iter(self.inputs)):'0'*64}),dict(source_sha256={})]
        for delta in variants:
            with self.subTest(delta=list(delta)):
                self.record.write_text(json.dumps(self.data|delta),encoding='utf-8')
                with self.assertRaises(ValueError):self.run_cli(['prepare',*self.base,'--disposable-development-site'])
                self.assertFalse(self.work.exists())

    def test_actual_image_apps_or_mismatched_native_identity_stop_before_resource_helper(self):
        for index,kind in enumerate(['extra_addon','native_mismatch','historical_reader']):
            if index:
                self.work=self.root/('refused-'+kind);self.base[1]=str(self.work)
            with self.subTest(kind=kind),self.external_boundaries():
                self.runtime['inventory']['native_addons']=dict.fromkeys(entry.ADDONS)
                self.runtime['native_manifests']['mp_core']['version']='19.0.0.2.3'
                self.runtime['platform_version']='0.2.3'
                if kind=='extra_addon':self.runtime['inventory']['native_addons']['mp_unexpected']=None
                elif kind=='native_mismatch':self.runtime['native_manifests']['mp_core']['version']='19.0.0.2.4'
                else:self.runtime['platform_version']='0.1.0'
                with self.assertRaises((ValueError,RuntimeError)):self.run_cli(['prepare',*self.base,'--disposable-development-site'])
                self.assertEqual(self.events,[])
                self.assertTrue((self.work/'intents/prepare.json').exists())

    def test_context_drift_and_existing_intent_refuse_before_initialize_or_command(self):
        with self.external_boundaries():
            self.run_cli(['prepare',*self.base,'--disposable-development-site'])
            path=self.work/'context.json';context=json.loads(path.read_bytes());context['port']=18991;entry.write(path,context)
            with self.assertRaisesRegex(ValueError,'receipt or files changed'):self.run_cli(['initialize','--workdir',str(self.work),'--disposable-development-site'])
            context['port']=18990;entry.write(path,context)
            site=entry.CandidateSite(self.work,context);site._intent('command-example')
            with patch.object(entry.Reference,'command',side_effect=AssertionError('Must not execute')):
                with self.assertRaisesRegex(RuntimeError,'already attempted'):site.command('example',['docker','run'])
        self.assertEqual([e[0] for e in self.events],['prepare'])

    def test_absence_requires_exact_not_found_not_permission_transport_or_empty(self):
        for code,stderr,success in [(1,b'Error response from daemon: network exact not found',True),(1,b'permission denied',False),(1,b'',False),(0,b'',False)]:
            result=subprocess.CompletedProcess([],code,stdout=b'[]',stderr=stderr)
            with self.subTest(stderr=stderr),patch.object(entry.subprocess,'run',return_value=result):
                if success:entry.docker_absent('network','exact')
                else:
                    with self.assertRaises(ValueError):entry.docker_absent('network','exact')

    def test_subnets_and_resource_metadata_drift_refuse_before_resource_creation(self):
        with self.assertRaises(ValueError):entry.selected_subnets('10.0.0.0/24','10.0.0.0/28')
        with self.assertRaises(ValueError):entry.selected_subnets('8.8.8.0/28','10.0.0.0/28')
        with self.external_boundaries():
            self.run_cli(['prepare',*self.base,'--disposable-development-site'])
            site=entry.CandidateSite(self.work,json.loads((self.work/'context.json').read_bytes()));state=site.state()
            with patch.object(entry,'docker_absent'),patch.object(entry.socket,'socket') as sock,patch.object(entry.subprocess,'check_output',side_effect=['network-id\n',json.dumps([dict(Id='wrong',IPAM=dict(Config=[]))]).encode()]):
                with self.assertRaisesRegex(ValueError,'Incomplete global'):site._resource_gate(state)
            self.assertNotIn('resource_gate',state)
            with patch.object(entry,'docker_absent') as absence,patch.object(entry.socket,'socket'),patch.object(entry.subprocess,'check_output',return_value=''):
                site._resource_gate(state)
                self.assertIn(state['project']+'-app-release-'+state['bootstrap_id'].replace('-',''),state['resource_gate']['exact_resources']['container'])
                self.assertEqual(absence.call_count,14)
        self.assertEqual(len(state['resource_gate']['exact_resources']['container']),6)

if __name__=='__main__':unittest.main()
