"""Exact staged-image pinning before native mutation; no plugin imports."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.approval_validation import IndependentValidator
from modular_platform.catalog import Catalog
from modular_platform.contracts import ContractError
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest
from modular_platform.release_staging import prepare_staged_plan,StageStore
from modular_platform.native_executor import NativeExecutor
from modular_platform.lifecycle_planning import installation_id
from test_plans import base_state,target,ident,STAMP,PROVENANCE
from test_resolution import ENVIRONMENT,plugin


def staged_runtime(catalog):
    artifacts={};files={}
    for item in catalog:
        plugin_id=item['manifest']['plugin']['id'];addon=item['manifest']['runtime']['addon_name'];filename=plugin_id+'.mplug'
        artifacts[plugin_id]={'digest':item['digest'],'file':filename,'plugin_id':plugin_id,'version':item['manifest']['plugin']['version'],'addon':addon}
        files['artifacts/'+filename]=item['digest'][7:]
        prefix='backend/odoo_addons/'+addon+'/'
        files.update({'addons/'+addon+'/'+name[len(prefix):]:digest for name,digest in item['inventory'].items() if name.startswith(prefix)})
    return {'inventory':{'artifacts':artifacts,'files':files,
            'native_addons':dict.fromkeys(['mp_core','mp_shell']+[item['manifest']['runtime']['addon_name'] for item in catalog]),
            'policy':{'upstream_commit':PROVENANCE['upstream_commit']},'generated_patches':[]},
        'inventory_digest':'sha256:'+'d'*64,'python_lock_digest':PROVENANCE['python_lock_digest'],
        'python':'3.12.16','architecture':'amd64','markers':ENVIRONMENT['markers'],
        'accepted_wheel_tags':ENVIRONMENT['accepted_wheel_tags'],'python_metadata':[],
        'modified_files':[],'unexpected_addon_files':[],'missing_addon_files':[]}


class StagedPlans(unittest.TestCase):
    def setUp(self):
        self.old=plugin('a');self.new=plugin('a','1.1.0');self.catalog=[self.old,self.new]
        self.document={'state':base_state([self.old]),'environment':ENVIRONMENT,'provenance':PROVENANCE,'python_metadata':[]}
        self.document['state'].update(bindings=[],endpoints=[])
        self.target=target(action='upgrade')
        self.document['state']['installations']=[{key:value for key,value in self.target.items() if key!='action'}|
            {'state':'installed','metadata_state':'installed','feature_state':'enabled'}]
        self.site={'site_id':ident(20),'workspaces':[{'workspace_id':ident(30),'state':'active'}],
            'installations':[{'plugin_id':'org.test.a','installation_id':ident(100),'metadata_state':'installed'}]}
        self.runtime=staged_runtime([self.new])
        self.descriptor={'stage_digest':'sha256:'+'c'*64,'base_image_id':'sha256:'+'a'*64,
            'target_image_id':'sha256:'+'b'*64,'inventory_digest':self.runtime['inventory_digest'],'runtime_digest':data_digest(self.runtime)}

    def prepare(self,**kwargs):
        return prepare_staged_plan(self.document,[self.site],self.catalog,self.runtime,self.descriptor,
            targets=kwargs.get('targets',[self.target]),operation_type='upgrade',operation_id=ident(500),created_at=STAMP)

    def validator(self):
        validator=object.__new__(IndependentValidator)
        class Snapshot:
            def snapshot(inner):return copy.deepcopy(self.catalog)
        class Observer:
            def read(inner):return {'sites':[copy.deepcopy(self.site)]}
            def state(inner,observation,catalog):return copy.deepcopy(self.document)
        class Stages:
            def load(inner,descriptor):
                if descriptor!=self.descriptor:raise OperatorError('Independent staged descriptor mismatch')
                return copy.deepcopy(self.descriptor),{'runtime':copy.deepcopy(self.runtime)}
        validator.catalog,validator.observer,validator.stage_store=Snapshot(),Observer(),Stages()
        return validator

    def test_exact_image_id_is_hash_bound_even_with_identical_source_inventory(self):
        bundle=self.prepare();self.assertEqual(self.validator()(bundle),self.document['state'])
        self.assertTrue(check_bundle(bundle,self.document['state']))
        self.assertEqual(bundle['display']['staged_image']['target_image_id'],self.descriptor['target_image_id'])
        self.assertEqual(bundle['plan']['artifacts'][0]['version'],'1.1.0')
        first=bundle['plan_hash'];self.descriptor['target_image_id']='sha256:'+'e'*64
        self.assertNotEqual(self.prepare()['plan_hash'],first)
        with self.assertRaisesRegex(OperatorError,'descriptor mismatch'):self.validator()(bundle)

    def test_forged_staged_pin_and_unknown_scope_fail_before_mutation(self):
        bundle=self.prepare();bundle['operation_lock']['staged_image']['target_image_id']='sha256:'+'e'*64
        with self.assertRaisesRegex(ContractError,'lock digest'):check_bundle(bundle,self.document['state'])
        with self.assertRaisesRegex(OperatorError,'current site/workspace'):self.prepare(targets=[self.target|{'workspace_id':ident(999)}])
        validator=self.validator();validator.stage_store=None
        with self.assertRaisesRegex(OperatorError,'independently owned'):validator(self.prepare())

    def test_current_image_executor_never_uses_old_image_for_a_staged_plan(self):
        executor=object.__new__(NativeExecutor)
        class Store:
            def bundle(inner,operation):return self.prepare()
        executor.store=Store()
        with self.assertRaisesRegex(OperatorError,'current-image mutation denied'):executor.apply(ident(500))

    def test_self_consistent_image_inventory_cannot_substitute_curated_native_bytes(self):
        from modular_platform.projection import runtime_inputs
        self.new['inventory']['backend/odoo_addons/test_a/models.py']='a'*64
        self.runtime=staged_runtime([self.new])
        runtime_inputs(self.runtime,self.catalog)
        self.runtime['inventory']['files']['addons/test_a/models.py']='b'*64
        with self.assertRaisesRegex(ContractError,'native source differs'):runtime_inputs(self.runtime,self.catalog)
        self.runtime=staged_runtime([self.new]);self.runtime['inventory']['files']['addons/test_a/extra.py']='c'*64
        with self.assertRaisesRegex(ContractError,'native source differs'):runtime_inputs(self.runtime,self.catalog)
        self.runtime=staged_runtime([self.new]);self.runtime['inventory']['files']['artifacts/org.test.a.mplug']='f'*64
        with self.assertRaisesRegex(ContractError,'package bytes differ'):runtime_inputs(self.runtime,self.catalog)

    def test_stage_does_not_implicitly_activate_existing_packaged_dependencies(self):
        a=plugin('a',depends={'b':'>=1'});b=plugin('b')
        self.catalog=[a,b];self.runtime=staged_runtime(self.catalog)
        self.descriptor.update(runtime_digest=data_digest(self.runtime))
        self.document['state']=base_state(self.catalog)|{'bindings':[],'endpoints':[]}
        self.site['installations']=[]
        with self.assertRaisesRegex(OperatorError,'required workspace dependency'):
            prepare_staged_plan(self.document,[self.site],self.catalog,self.runtime,self.descriptor,
                targets=[target()|{'installation_id':installation_id(self.site,'org.test.a')}],
                operation_type='install',operation_id=ident(500),created_at=STAMP)

    def test_upgrade_derives_exact_new_capability_and_independent_recompute_rejects_omission(self):
        request={'capability':'org.test.a:records.read','scope':'workspace','reason':'reviewed integration'}
        self.new['manifest']['permissions']['requests']=[request]
        self.runtime=staged_runtime([self.new]);self.descriptor['runtime_digest']=data_digest(self.runtime)
        bundle=self.prepare()
        self.assertEqual(bundle['plan']['permission_changes'],[{'plugin_id':'org.test.a','workspace_id':ident(30),
            'capability':request['capability'],'action':'grant'}])
        self.validator()(bundle)
        # Rehashing the envelope does not permit a proposal to hide a grant.
        from modular_platform.plans import plan_hash,_display
        bundle['plan']['permission_changes']=[]
        bundle['plan_hash']=plan_hash(bundle['plan']);bundle['display']=_display(bundle['plan'],bundle['operation_lock'])
        with self.assertRaises(OperatorError):self.validator()(bundle)

    def test_install_does_not_silently_reapprove_existing_revoked_capability(self):
        request={'capability':'org.test.a:records.read','scope':'workspace','reason':'integration'}
        self.new['manifest']['permissions']['requests']=[request]
        self.runtime=staged_runtime([self.new]);self.descriptor['runtime_digest']=data_digest(self.runtime)
        self.site['workspaces'].append({'workspace_id':ident(31),'state':'active'})
        target_b=self.target|{'action':'install','workspace_id':ident(31)}
        self.site['grants']=[{'workspace_id':ident(31),'installation_id':ident(100),'capability':request['capability'],'state':'revoked'}]
        # This fixture already has the new artifact in the release; adding a
        # workspace feature must preserve a prior explicit revocation there.
        self.document['state']['release_lock']=base_state([self.new])['release_lock']
        self.document['state']['release_digest']=data_digest(self.document['state']['release_lock'])
        bundle=prepare_staged_plan(self.document,[self.site],self.catalog,self.runtime,self.descriptor,
            targets=[target_b],operation_type='install',operation_id=ident(500),created_at=STAMP)
        self.assertEqual(bundle['plan']['permission_changes'],[])


class PrivateStageStore(unittest.TestCase):
    def test_actual_immutable_private_record_rejects_image_or_base_configuration_substitution(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=OperatorStore.initialize(Path(temporary)/'control',{ident(10):[ident(20)]})
            configuration={'schema_version':1,'deployment_id':ident(10),'project':'mp-r0-r1staging',
                'sites':[{'site_id':ident(20),'database':'mp_disposable_r0_r1_staging'}],
                'image_id':'sha256:'+'a'*64,'generation':1,'policy_version':1,'operator_authorization_generation':1,'release_created_at':STAMP}
            catalog=[plugin('a')];runtime=staged_runtime(catalog)
            class Snapshot:
                def snapshot(self):return copy.deepcopy(catalog)
            stages=StageStore(store,configuration,Snapshot())
            with patch('modular_platform.release_staging.DockerObserver.read',return_value={}),patch('modular_platform.release_staging.inspect_image',return_value=runtime):
                descriptor=stages.stage('sha256:'+'b'*64)
                actual,record=stages.load(descriptor)
                self.assertEqual(actual,descriptor);self.assertEqual(record['runtime'],runtime)
                with self.assertRaisesRegex(OperatorError,'selected staged release changed'):
                    stages.load(descriptor|{'target_image_id':'sha256:'+'e'*64})
                stages.configuration=configuration|{'generation':2}
                with self.assertRaisesRegex(OperatorError,'stale deployment'):stages.load(descriptor)


if __name__=='__main__':unittest.main()
