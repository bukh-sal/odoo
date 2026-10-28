"""Manager proposals use the real planner and independent reconstruction."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.contracts import ContractError
from modular_platform.manager_planning import candidate_preview,prepare_manager_native
from modular_platform.plans import data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.resolution import PlanningError
import test_release_staging as staging
from test_release_staging import staged_runtime
from test_plans import ident,STAMP,base_state
from test_resolution import plugin


class ManagerPlans(unittest.TestCase):
    def setUp(self):
        self.fixture=staging.StagedPlans();self.fixture.setUp();self.f=self.fixture
        self.f.document['state']['image_id']=self.f.descriptor['base_image_id']
        self.nomination={'schema_version':1,'operation':'prepare','operation_type':'upgrade',
            'plugin_id':'org.test.a','site_id':ident(20),'workspace_ids':[ident(30)],'cascade':False,
            'artifact_version':'1.1.0','artifact_digest':self.f.new['digest']}

    def prepare(self):
        return prepare_manager_native(self.f.document,[self.f.site],self.f.catalog,self.f.base,
            {'descriptor':self.f.descriptor,'runtime':self.f.runtime},self.nomination,
            operation_id=ident(500),created_at=STAMP)

    def test_upgrade_reconstructs_independently_and_does_not_mutate_inputs(self):
        before=copy.deepcopy(self.f.document)
        bundle=self.prepare()
        self.assertEqual(self.f.validator()(bundle),self.f.document['state'])
        self.assertEqual(bundle,self.f.prepare());self.assertEqual(self.f.document,before)

    def test_shared_upgrade_includes_all_suspended_scopes(self):
        original=self.f.document['state']['installations'][0]
        self.f.document['state']['installations'].append(original|{'workspace_id':ident(31),'feature_state':'suspended'})
        self.f.site['workspaces'].append({'workspace_id':ident(31),'state':'active'})
        bundle=self.prepare()
        self.assertEqual({item['workspace_id'] for item in bundle['operation_lock']['targets']},{ident(30),ident(31)})
        self.assertEqual(self.f.validator()(bundle),self.f.document['state'])

    def test_wrong_artifact_same_version_and_unknown_scope_fail_closed(self):
        for fields in [{'artifact_digest':'sha256:'+'f'*64},{'artifact_version':'1.0.0'},
                       {'workspace_ids':[ident(999)]},{'workspace_ids':[]}]:
            with self.subTest(fields=fields):
                old=self.nomination;self.nomination=old|fields
                with self.assertRaises((PlanningError,ContractError)):self.prepare()
                self.nomination=old

    def test_browser_cannot_supply_image_command_identity_or_approval(self):
        for key in ['image_id','command','installation_id','approved','staged_release']:
            original=self.nomination;self.nomination=original|{key:'forged'}
            with self.assertRaises(ContractError):self.prepare()
            self.nomination=original
        bundle=self.prepare();self.f.descriptor['target_image_id']='sha256:'+'f'*64
        with self.assertRaisesRegex(ContractError,'descriptor mismatch'):self.f.validator()(bundle)

    def test_current_image_install_uses_same_stage_and_permission_review(self):
        self.f.runtime=self.f.base;self.f.descriptor.update(target_image_id=self.f.descriptor['base_image_id'],
            inventory_digest=self.f.runtime['inventory_digest'],runtime_digest=data_digest(self.f.runtime))
        self.f.document['state']['installations']=[];self.f.site['installations']=[]
        self.nomination.update(operation_type='install',artifact_version='1.0.0',artifact_digest=self.f.old['digest'])
        bundle=self.prepare()
        self.assertEqual(bundle['operation_lock']['targets'][0]['action'],'install')
        self.assertEqual(self.f.validator()(bundle),self.f.document['state'])

    def test_transitive_install_needs_consent_and_lists_exact_new_scope(self):
        a=plugin('a',depends={'b':'>=1'});b=plugin('b')
        self.f.catalog=[a,b];self.f.base=staged_runtime([a,b]);self.f.runtime=self.f.base
        self.f.document['state']=base_state([a,b])|{'image_id':self.f.descriptor['base_image_id'],'bindings':[],'endpoints':[]}
        self.f.site['installations']=[]
        self.f.descriptor.update(target_image_id=self.f.descriptor['base_image_id'],runtime_digest=data_digest(self.f.runtime))
        self.nomination.update(operation_type='install',artifact_version='1.0.0',artifact_digest=a['digest'])
        with self.assertRaisesRegex(PlanningError,'consent'):self.prepare()
        self.nomination['cascade']=True;bundle=self.prepare()
        self.assertEqual({row['plugin_id'] for row in bundle['operation_lock']['targets']},{'org.test.a','org.test.b'})
        self.assertEqual(self.f.validator()(bundle),self.f.document['state'])

    def test_stale_or_fabricated_preview_does_not_become_authority(self):
        for descriptor in [self.f.descriptor|{'base_image_id':'sha256:'+'f'*64},
                           self.f.descriptor|{'runtime_digest':'sha256:'+'f'*64}]:
            with self.assertRaises(PlanningError):candidate_preview(descriptor,self.f.runtime,self.f.document['state']['image_id'])
        with self.assertRaisesRegex(PlanningError,'stage and publish'):
            prepare_manager_native(self.f.document,[self.f.site],self.f.catalog,self.f.base,None,self.nomination,
                operation_id=ident(500),created_at=STAMP)

    def test_publication_excludes_operator_configuration_and_clears_stage_by_default(self):
        f=self.f
        class Observer:
            config={'image_id':f.descriptor['base_image_id'],'sites':[{'site_id':ident(20),'secret_reference':'operator-only'}]}
            def read(self):return {'runtime':f.base}
            def state(self,observation,snapshot):return f.document
            def _container(self,name):return 'fixed-app'
        class Catalog:
            def snapshot(self):return f.catalog
        public={'configuration':{'site_ids':[ident(20)]},'runtime':f.base,'catalog':f.catalog}
        seen=[]
        def write(arguments,*,input):
            seen.append(json.loads(input));return b'{"profile_published":true}'
        staged=(f.descriptor,{'base_configuration':Observer.config,'runtime':f.runtime,'private_path':'never-publish'})
        with patch('modular_platform.profile_channel.public_profile',side_effect=lambda *args:copy.deepcopy(public)),patch('modular_platform.profile_channel._run',side_effect=write):
            publish_profile(Observer(),Catalog(),staged=staged);publish_profile(Observer(),Catalog())
        self.assertEqual(set(seen[0]['staged_release']),{'descriptor','runtime'})
        self.assertNotIn('operator-only',json.dumps(seen));self.assertNotIn('never-publish',json.dumps(seen))
        self.assertNotIn('staged_release',seen[1])


if __name__=='__main__':unittest.main()
