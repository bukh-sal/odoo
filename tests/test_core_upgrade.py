"""Explicit core maintenance cannot masquerade as a static or plugin update."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.contracts import ContractError,validate,plan_hash
from modular_platform.native_executor import native_maintenance_flags
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest,_display
from modular_platform.release_staging import prepare_staged_plan,validate_core_upgrade,validate_platform_deploy,validate_plugin_core_stability
import test_platform_deploy as deploy
import test_release_staging as staged
from test_plans import ident,STAMP


class CoreUpgrade(unittest.TestCase):
    pin=deploy.PlatformDeploy.pin

    def setUp(self):
        deploy.PlatformDeploy.setUp(self)
        for runtime in [self.base,self.runtime]:
            for manifest in runtime['native_manifests'].values():manifest['version']='19.0.0.1.1'
            runtime['inventory']['files']['addons/mp_shell/__manifest__.py']='a'*64
        self.runtime['native_manifests']['mp_shell']['version']='19.0.0.1.2'
        self.runtime['inventory']['files']['addons/mp_shell/__manifest__.py']='b'*64
        self.runtime['inventory']['files']['addons/mp_shell/controllers.py']='c'*64
        self.site['native_modules']=[{'addon':name,'state':'installed','version':manifest['version']}
            for name,manifest in self.base['native_manifests'].items()]

    def prepare(self,targets=None):
        self.pin()
        return prepare_staged_plan(self.document,[self.site],self.catalog,self.runtime,self.descriptor,
            targets=[self.target] if targets is None else targets,operation_type='core_upgrade',
            operation_id=ident(500),created_at=STAMP,base_runtime=self.base)

    def test_exact_core_versions_sources_and_destructive_approval(self):
        bundle=self.prepare();validate('plan',bundle['plan']);check_bundle(bundle,self.document['state'])
        self.assertEqual(bundle['display']['native_core_changes'],[{'addon':'mp_shell','previous_version':'19.0.0.1.1',
            'target_version':'19.0.0.1.2','migrations':[]}])
        self.assertTrue(bundle['plan']['backup']['required']);self.assertTrue(bundle['plan']['destructive'])
        self.assertEqual(native_maintenance_flags(bundle,{}),['-u','mp_shell'])
        for destructive,trust in [(False,False),(True,False),(False,True)]:
            with self.subTest(destructive=destructive,trust=trust),self.assertRaises(OperatorError):
                OperatorStore._check_acks(bundle,{'destructive':destructive,'trust_expansion':trust,'permission_expansion':False})
        OperatorStore._check_acks(bundle,{'destructive':True,'trust_expansion':True,'permission_expansion':False})

    def test_independent_reconstruction_rejects_rehashed_core_version_forgery(self):
        bundle=self.prepare();validator=staged.StagedPlans.validator(self)
        validator.observer.read=lambda:{'sites':[copy.deepcopy(self.site)],'runtime':copy.deepcopy(self.base)}
        self.assertEqual(validator(bundle),self.document['state'])
        forged=copy.deepcopy(bundle);forged['operation_lock']['native_core_changes'][0]['target_version']='19.0.99.0.0'
        forged['plan']['dependency_lock_digest']=data_digest(forged['operation_lock']);forged['plan_hash']=plan_hash(forged['plan'])
        forged['display']=_display(forged['plan'],forged['operation_lock'])
        with self.assertRaisesRegex(OperatorError,'reconstruction'):validator(forged)

    def test_unversioned_downgrade_noncanonical_and_upstream_changes_deny(self):
        for case in ['same','downgrade','noncanonical','upstream','unlisted','manifest_hash']:
            runtime=copy.deepcopy(self.runtime)
            if case in ['same','downgrade','noncanonical']:
                runtime['native_manifests']['mp_shell']['version']={'same':'19.0.0.1.1','downgrade':'19.0.0.1.0','noncanonical':'19.0.00.1.2'}[case]
            elif case=='manifest_hash':runtime['inventory']['files']['addons/mp_shell/__manifest__.py']='a'*64
            else:runtime['inventory']['files']['odoo/http.py' if case=='upstream' else 'addons/mp_other/controllers.py']='d'*64
            with self.subTest(case=case),self.assertRaises(OperatorError):validate_core_upgrade(self.base,runtime,self.descriptor)
        with self.assertRaises(OperatorError):validate_core_upgrade(None,self.runtime,self.descriptor)
        with self.assertRaises(OperatorError):validate_core_upgrade(self.base,self.runtime,self.descriptor|{'target_image_id':self.descriptor['base_image_id']})

    def test_package_python_dependency_and_policy_changes_deny(self):
        for case in ['artifact','python','lock','dependency','policy']:
            runtime=copy.deepcopy(self.runtime)
            if case=='artifact':next(iter(runtime['inventory']['artifacts'].values()))['digest']='sha256:'+'d'*64
            elif case=='python':runtime['python_metadata']=[{'name':'unexpected'}]
            elif case=='lock':runtime['python_lock_digest']='sha256:'+'d'*64
            elif case=='dependency':runtime['inventory']['native_addons']['mp_shell']={'depends':['unknown']}
            else:runtime['inventory']['policy']['profile']='unreviewed'
            with self.subTest(case=case),self.assertRaises(OperatorError):validate_core_upgrade(self.base,runtime,self.descriptor)

    def test_migration_digests_and_historical_script_immutability(self):
        current='addons/mp_shell/migrations/19.0.0.1.2/post-release.py'
        self.runtime['inventory']['files'][current]='d'*64
        self.assertEqual(self.prepare()['display']['native_core_changes'][0]['migrations'],[{'path':current,'sha256':'d'*64}])
        old='addons/mp_shell/migrations/19.0.0.1.1/post-release.py'
        self.base['inventory']['files'][old]='e'*64;self.runtime['inventory']['files'][old]='e'*64
        self.prepare()
        for digest in ['f'*64,None]:
            if digest is None:self.runtime['inventory']['files'].pop(old)
            else:self.runtime['inventory']['files'][old]=digest
            with self.assertRaisesRegex(OperatorError,'previously applicable'):self.prepare()

    def test_database_versions_pending_native_state_and_omitted_scope_deny(self):
        native=next(row for row in self.site['native_modules'] if row['addon']=='mp_shell')
        for patch in [{'version':'19.0.0.0.1'},{'state':'to upgrade'}]:
            prior=copy.deepcopy(native);native.update(patch)
            with self.assertRaisesRegex(OperatorError,'base database versions'):self.prepare()
            native.clear();native.update(prior)
        second=self.document['state']['installations'][0]|{'workspace_id':ident(31)}
        self.document['state']['installations'].append(second)
        with self.assertRaisesRegex(ContractError,'every installed'):self.prepare()

    def test_static_deploy_and_plugin_operations_cannot_invoke_core_maintenance(self):
        with self.assertRaises(OperatorError):validate_platform_deploy(self.base,self.runtime,self.descriptor)
        with self.assertRaisesRegex(OperatorError,'Plugin operation cannot carry'):validate_plugin_core_stability(self.base,self.runtime)
        bundle=self.prepare()
        for operation in ['deploy','upgrade']:
            forged=copy.deepcopy(bundle);forged['plan']['operation_type']=operation
            with self.assertRaises(OperatorError):native_maintenance_flags(forged,{})
        bundle['operation_lock']['targets'][0]['action']='upgrade'
        with self.assertRaises(OperatorError):native_maintenance_flags(bundle,{'org.test.a':self.old})

    def test_app_requests_reject_core_operation_but_status_can_show_it(self):
        examples=ROOT/'packages/contracts/examples/v1'
        request=json.loads((examples/'operations-request.json').read_text());request['operation_type']='core_upgrade'
        with self.assertRaises(ContractError):validate('operations-request',request)
        view=json.loads((examples/'operations-view.json').read_text())
        view['plan']=json.loads((examples/'plan-core-upgrade.json').read_text())
        for row in view['targets']:row['action']='deploy'
        validate('operations-view',view)


if __name__=='__main__':unittest.main()
