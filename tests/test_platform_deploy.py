"""Platform-only image deployment preserves strict plugin upgrade semantics."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.approval_validation import IndependentValidator
from modular_platform.contracts import ContractError,validate
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest,applicable_migrations
from modular_platform.release_staging import prepare_staged_plan,validate_platform_deploy
import test_release_staging as staged
from test_plans import ident,STAMP


class PlatformDeploy(unittest.TestCase):
    def setUp(self):
        staged.StagedPlans.setUp(self)
        self.runtime=staged.staged_runtime([self.old])
        self.runtime['native_manifests']={name:{'version':'19.0.1.0','assets':{}} for name in self.runtime['inventory']['native_addons']}
        self.runtime['inventory']['files']['addons/mp_shell/static/src/host.js']='1'*64
        self.base=copy.deepcopy(self.runtime)
        self.runtime['inventory']['files']['addons/mp_shell/static/src/host.js']='2'*64
        self.target['action']='deploy';self.pin()

    def pin(self):self.descriptor['runtime_digest']=data_digest(self.runtime)

    def prepare(self,targets=None):
        self.pin()
        return prepare_staged_plan(self.document,[self.site],self.catalog,self.runtime,self.descriptor,
            targets=[self.target] if targets is None else targets,operation_type='deploy',operation_id=ident(500),created_at=STAMP,base_runtime=self.base)

    def test_deploy_pins_source_diff_checkpoint_restart_and_unchanged_package(self):
        bundle=self.prepare();validate('plan',bundle['plan']);check_bundle(bundle,self.document['state'])
        self.assertEqual(bundle['plan']['operation_type'],'deploy');self.assertEqual(bundle['plan']['artifacts'][0]['version'],'1.0.0')
        self.assertEqual(bundle['plan']['artifacts'][0]['migration_digests'],[])
        self.assertTrue(bundle['plan']['backup']['required']);self.assertTrue(bundle['display']['restart_required'])
        self.assertEqual(bundle['display']['platform_source_diff'],[{'path':'addons/mp_shell/static/src/host.js','previous_sha256':'1'*64,'target_sha256':'2'*64}])
        with self.assertRaisesRegex(OperatorError,'acknowledgment'):OperatorStore._check_acks(bundle,{'destructive':False,'trust_expansion':False,'permission_expansion':False})
        OperatorStore._check_acks(bundle,{'destructive':False,'trust_expansion':True,'permission_expansion':False})

    def test_independent_reconstruction_binds_source_diff_and_base_runtime(self):
        bundle=self.prepare();validator=staged.StagedPlans.validator(self)
        def read():return {'sites':[copy.deepcopy(self.site)],'runtime':copy.deepcopy(self.base)}
        validator.observer.read=read
        self.assertEqual(validator(bundle),self.document['state'])
        forged=copy.deepcopy(bundle);forged['operation_lock']['platform_source_diff'][0]['target_sha256']='3'*64
        with self.assertRaisesRegex(ContractError,'digest'):check_bundle(forged,self.document['state'])
        validator.observer.read=lambda:{'sites':[self.site]}
        with self.assertRaisesRegex(OperatorError,'observed base'):validator(bundle)

    def test_same_image_no_op_and_unknown_native_changes_denied(self):
        for case in ['same_image','no_change','native_python','native_data','upstream','unknown_root']:
            runtime=copy.deepcopy(self.runtime);descriptor=copy.deepcopy(self.descriptor)
            if case=='same_image':descriptor['target_image_id']=descriptor['base_image_id']
            elif case=='no_change':runtime=copy.deepcopy(self.base)
            else:
                name={'native_python':'addons/mp_shell/models.py','native_data':'addons/mp_shell/views/bootstrap.xml',
                    'upstream':'odoo/tools/config.py','unknown_root':'unknown.py'}[case]
                runtime['inventory']['files'][name]='4'*64
            with self.subTest(case=case),self.assertRaises(OperatorError):validate_platform_deploy(self.base,runtime,descriptor)

    def test_package_python_manifest_and_policy_changes_denied(self):
        for case in ['artifact','python','lock','manifest','policy','addon']:
            runtime=copy.deepcopy(self.runtime)
            if case=='artifact':next(iter(runtime['inventory']['artifacts'].values()))['digest']='sha256:'+'4'*64
            elif case=='python':runtime['python_metadata']=[{'name':'unexpected'}]
            elif case=='lock':runtime['python_lock_digest']='sha256:'+'4'*64
            elif case=='manifest':runtime['native_manifests']['mp_shell']['version']='19.0.2.0'
            elif case=='policy':runtime['inventory']['policy']['profile']='unreviewed'
            else:runtime['inventory']['native_addons']['unknown']={}
            with self.subTest(case=case),self.assertRaises(OperatorError):validate_platform_deploy(self.base,runtime,self.descriptor)
        self.runtime['native_manifests']['mp_shell']['assets']={'bundle':['new.js']}
        self.runtime['inventory']['files']['addons/mp_shell/__manifest__.py']='5'*64
        self.assertEqual(len(validate_platform_deploy(self.base,self.runtime,self.descriptor)),2)

    def test_omitted_scope_and_changed_plugin_deny_without_version_exception(self):
        second={key:value for key,value in self.document['state']['installations'][0].items()}|{'workspace_id':ident(31)}
        self.document['state']['installations'].append(second)
        with self.assertRaisesRegex(ContractError,'every installed'):self.prepare()
        self.document['state']['installations'].pop()
        self.runtime=staged.staged_runtime([self.new]);self.runtime['native_manifests']=self.base['native_manifests']
        with self.assertRaises(OperatorError):self.prepare()
        with self.assertRaisesRegex(ContractError,'strictly increase'):applicable_migrations(self.old['manifest'],'1.0.0')

    def test_public_status_can_show_deploy_but_app_cannot_request_it(self):
        import json
        examples=ROOT/'packages/contracts/examples/v1'
        view=json.loads((examples/'operations-view.json').read_text())
        view['plan']=json.loads((examples/'plan-deploy.json').read_text())
        for row in view['targets']:row['action']='deploy'
        validate('operations-view',view)
        request=json.loads((examples/'operations-request.json').read_text());request['operation_type']='deploy'
        with self.assertRaises(ContractError):validate('operations-request',request)


if __name__=='__main__':unittest.main()
