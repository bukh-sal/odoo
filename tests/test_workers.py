"""Fail before native startup, preserve feature states and bind retained workers."""
import configparser
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import verify_native_state
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.restore_executor import recovery_configuration,restored_release_sql
from modular_platform.worker_start import validate
from modular_platform.workers import ensure
from test_plans import ident,STAMP


def configuration():
    return {'schema_version':1,'deployment_id':ident(10),'project':'mp-r0-r1workers',
        'sites':[{'site_id':ident(20),'database':'mp_disposable_r0_r1_workers'}],
        'image_id':'sha256:'+'a'*64,'generation':3,'policy_version':1,
        'operator_authorization_generation':1,'release_created_at':STAMP}


class Cursor:
    def __init__(self,pin,modules):self.pin,self.modules=pin,modules
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql):pass
    def fetchone(self):return (self.pin,) if self.pin else None
    def fetchall(self):return self.modules


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        addon=self.root/'addons/test_guard';addon.mkdir(parents=True)
        # This module would fail loudly if validation imported plugin code.
        (addon/'__init__.py').write_text("raise RuntimeError('must never import plugin')")
        (addon/'__manifest__.py').write_text("{'version':'1.2.3'}")
        files={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in addon.iterdir()}
        raw=json.dumps({'files':files,'native_addons':{'test_guard':{}}}).encode()
        (self.root/'distribution-inventory.json').write_bytes(raw)
        self.pin='sha256:'+hashlib.sha256(raw).hexdigest()
        options=configparser.ConfigParser();options['options']={'db_name':'fixed_database','addons_path':'/opt/modular/addons',
            'server_wide_modules':'base,web','list_db':'False','max_cron_threads':'0'}
        self.options=options['options'];self.cursor=Cursor(self.pin,[('test_guard','installed','19.0.1.2.3')])

    def cursor(self):return self.cursor

    def run_validation(self):
        class Connection:
            def cursor(inner):return self.cursor
        return validate(self.root,self.options,Connection(),'fixed_database',self.pin)

    def test_validates_data_only_without_importing_native_addons(self):
        self.assertEqual(self.run_validation(),self.pin)

    def test_pin_source_and_extra_addon_tampering_are_rejected(self):
        original=self.pin;self.pin='sha256:'+'b'*64
        with self.assertRaisesRegex(ValueError,'inventory pin mismatch'):self.run_validation()
        self.pin=original
        extra=self.root/'addons/test_guard/extra.py';extra.write_text('pass')
        with self.assertRaisesRegex(ValueError,'search-path content'):self.run_validation()
        extra.unlink();(self.root/'addons/test_guard/__init__.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'source differs'):self.run_validation()

    def test_wrong_database_pending_states_and_version_mismatch_never_start_migrations(self):
        self.cursor.pin=None
        with self.assertRaisesRegex(ValueError,'controlled maintenance'):self.run_validation()
        self.cursor.pin=self.pin
        for state,version in [('to upgrade','19.0.1.2.3'),('to install','19.0.1.2.3'),
            ('to remove','19.0.1.2.3'),('installed','19.0.1.2.2')]:
            self.cursor.modules=[('test_guard',state,version)]
            with self.subTest(state=state,version=version),self.assertRaisesRegex(ValueError,'never performs migration'):self.run_validation()

    def test_unsafe_boot_options_are_rejected(self):
        for key,value in [('init','test_guard'),('update','all'),('addons_path','/tmp/addons'),
            ('list_db','True'),('server_wide_modules','base,web,other'),('max_cron_threads','1'),('db_name','other')]:
            original=dict(self.options);self.options[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'bootstrap configuration'):self.run_validation()
            self.options.clear();self.options.update(original)


class WorkerAndRecoveryTests(unittest.TestCase):
    def test_retained_same_image_worker_selection_requires_exact_private_id(self):
        config=configuration();first='1'*64;second='2'*64
        def run(args):
            if args[1]=='ps':return (first[:12]+'\n'+second[:12]).encode()
            return json.dumps(config['image_id']).encode()
        with patch('modular_platform.deployment._run',side_effect=run):
            with self.assertRaisesRegex(ValueError,'Exactly one'):DockerObserver(config)._container('app',stopped=True)
            self.assertEqual(DockerObserver(config|{'worker_id':second})._container('app',stopped=True),second[:12])
        with self.assertRaisesRegex(ValueError,'selected worker'):DockerObserver(config|{'worker_id':second[:12]})

    def test_running_worker_prevents_creation_before_any_docker_mutation(self):
        config=configuration()
        with patch('modular_platform.workers.snapshots',return_value=[{'running':True}]),patch('modular_platform.workers._run') as run:
            with self.assertRaisesRegex(OperatorError,'must drain'):ensure(config,config['image_id'],ident(500),inventory_digest='sha256:'+'d'*64)
            run.assert_not_called()

    def test_fresh_worker_retains_and_disconnects_stopped_old_worker(self):
        config=configuration();old='1'*64;new='2'*64;network=config['project']+'_runtime';calls=[]
        def run(args):
            calls.append(args)
            if args[1]=='create':return new.encode()
            if args[1]=='inspect':return json.dumps([{'NetworkSettings':{'Networks':{network:{}}}}]).encode()
            return b''
        with patch('modular_platform.workers.snapshots',return_value=[{'container_id':old,'running':False,'networks':[network]}]),patch('modular_platform.workers._run',side_effect=run):
            self.assertEqual(ensure(config,config['image_id'],ident(500),inventory_digest='sha256:'+'d'*64),new)
        self.assertEqual(calls[1],['docker','network','disconnect',network,old])
        self.assertFalse(any('rm' in row or 'start' in row for row in calls))
        self.assertIn('--read-only',calls[0]);self.assertIn('10001:10001',calls[0])

    def test_recovery_accepts_only_exact_base_or_privately_recorded_approved_target(self):
        base=configuration();image='sha256:'+'b'*64;worker='2'*64
        lock={'core_inventory_digest':'sha256:'+'d'*64,'generation':3,'created_at':STAMP}
        manifest={'configuration':base,'previous_release':{'release_lock':lock}}
        bundle={'plan':{'created_at':STAMP},'operation_lock':{'release':{'generation':4},'staged_image':{'target_image_id':image}}}
        replacement=dict(base,image_id=image,generation=4,worker_id=worker,release_created_at=STAMP)
        record={'container_id':worker,'configuration':replacement,'previous_image_id':base['image_id']}
        target,restored=recovery_configuration(base,manifest,bundle)
        self.assertEqual(target['image_id'],base['image_id']);self.assertEqual(target['generation'],5)
        self.assertNotIn('worker_id',target);self.assertEqual(restored['generation'],5)
        self.assertEqual(recovery_configuration(replacement,manifest,bundle,record),(target,restored))
        for current,actual_record in [(replacement,None),(replacement|{'generation':5},record),
            (replacement,record|{'previous_image_id':image}),
            (replacement,record|{'configuration':replacement|{'sites':[{'site_id':ident(21),'database':'other'}]}})]:
            with self.subTest(current=current),self.assertRaisesRegex(OperatorError,'configuration|replacement'):
                recovery_configuration(current,manifest,bundle,actual_record)
        self.assertIn(data_digest(restored),restored_release_sql(target,restored,ident(500)))
        self.assertEqual(manifest['previous_release']['release_lock']['generation'],3)

    def test_readiness_preserves_suspended_scopes_and_checks_exact_grants(self):
        prior={'installation_id':ident(100),'workspace_id':ident(30),'site_id':ident(20),'plugin_id':'org.test.a',
            'state':'installed','feature_state':'suspended','metadata_state':'installed'}
        state={'release_digest':'sha256:'+'d'*64,'installations':[copy.deepcopy(prior)],'bindings':[]}
        change={'plugin_id':'org.test.a','workspace_id':ident(30),'capability':'notes.read','action':'grant'}
        bundle={'plan':{'target_release_digest':state['release_digest'],'permission_changes':[change],'policy_version':1},
            'operation_lock':{'targets':[{key:value for key,value in prior.items() if key in ('installation_id','workspace_id','site_id','plugin_id')}|{'action':'upgrade'}],'bindings':[]}}
        observation={'sites':[{'site_id':ident(20),'grants':[{'workspace_id':ident(30),'installation_id':ident(100),
            'capability':'notes.read','state':'approved','policy_version':1}]}]}
        verify_native_state(bundle,state,{'installations':[prior]},observation)
        state['installations'][0]['feature_state']='enabled'
        with self.assertRaisesRegex(OperatorError,'preserved availability'):verify_native_state(bundle,state,{'installations':[prior]},observation)
        state['installations'][0]['feature_state']='suspended';observation['sites'][0]['grants'][0]['state']='revoked'
        with self.assertRaisesRegex(OperatorError,'permission metadata'):verify_native_state(bundle,state,{'installations':[prior]},observation)


if __name__=='__main__':unittest.main()
