"""Real transition guards with substituted independent IO; no live qualification."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_external_projection as fixtures
from test_plans import ident
from modular_platform.plans import data_digest
from modular_platform.operator_os import OperatorError
from modular_platform.worker_transition import reviewed_worker_transition
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.dispatch_lifecycle import _reference,LifecycleScope,DispatchLifecycleError


class WorkerTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ExternalProjection.setUpClass()

    def setUp(self):
        self.f=fixtures.ExternalProjection();self.f.setUp()
        self.f.site=copy.deepcopy(self.f.site)
        self.f.config['project']='mp-disposable-transition-unit'
        self.row=self.f.site['installations'][1]
        self.f.site['features'][1]['feature_state']='suspended'
        self.old=copy.deepcopy(self.f.config['published_release'])
        self.new=copy.deepcopy(self.f.external)
        self.new['manifest']['plugin']['version']='99.0.0'
        self.image='modular-document-stats@sha256:'+'7'*64
        self.new['manifest']['external_service']['expected_image']=self.image
        self.new['digest']='sha256:'+'8'*64
        self.f.catalog.append(self.new)
        self.target=copy.deepcopy(self.old)
        pin=next(p for p in self.target['plugins'] if p['plugin_id']==self.row['plugin_id'])
        pin.update(version='99.0.0',digest=self.new['digest'],manifest_digest=data_digest(self.new['manifest']))
        self.f.endpoint['expected_image_digest']=self.image.split('@')[1]
        next(iter(self.f.external_state['service_health'].values()))['expected_image_digest']=self.image.split('@')[1]
        self.op=ident(500)
        self.lock=dict(operation_id=self.op,release=self.target,targets=[dict(installation_id=self.row['installation_id'],
            site_id=self.f.site['site_id'],workspace_id=ident(30),plugin_id=self.row['plugin_id'],action='upgrade')],endpoints=[copy.deepcopy(self.f.endpoint)])
        self.plan=dict(operation_id=self.op,operation_type='upgrade',deployment_id=self.f.config['deployment_id'],
            site_ids=[self.f.site['site_id']],base_release_digest=data_digest(self.old),target_release_digest=data_digest(self.target),
            artifacts=[dict(runtime='external_service')])
        self.bundle=dict(plan=self.plan,operation_lock=self.lock,plan_hash='sha256:'+'9'*64)
        self.native=Mock();self.native.config=self.f.config;self.native.target_path=Path('private/target.json')
        self.native.store.bundle.side_effect=lambda op:copy.deepcopy(self.bundle)
        self.native.store.status.return_value=dict(state='approved')
        self.reader=Mock();self.reader.config=dict(runtime=dict(image=self.image));self.reader.target=self.f.config
        self.reader.publisher._document.return_value=dict(generation=7,endpoints=[])
        self.reader.planning_state.side_effect=lambda:copy.deepcopy(self.f.external_state)

    def proof(self,*,recovery=False):
        return reviewed_worker_transition(self.native,self.op,self.old,self.f.config,self.row,self.f.site,
            self.f.catalog,self.reader,self.f.external_state,recovery=recovery)

    def policy(self,operation=True):
        with patch('modular_platform.reference_dispatch.WorkerPlanningReader',return_value=self.reader),\
                patch('modular_platform.reference_dispatch.read_metadata',return_value=self.f.site),\
                patch('modular_platform.reference_dispatch.Catalog') as catalog,\
                patch('modular_platform.reference_dispatch.private_json',side_effect=lambda p:self.reader.config if p.name=='worker-target.json' else self.f.config):
            catalog.return_value.snapshot.return_value=self.f.catalog
            return ReferenceDispatchMaintenance(self.native,operation=self.op if operation else None).reference_policy(self.f.config)

    def test_exact_stored_upgrade_allows_only_suspended_mismatch(self):
        value=self.policy();self.assertEqual(value['profile'],'r1-reference-stateless-transition-v1')
        self.assertEqual(value['worker_transition'],self.proof())
        self.native.store._authorize_plan.assert_called()
        with self.assertRaisesRegex(OperatorError,'exact independently'):self.policy(operation=False)
        self.native.store.status.return_value=dict(state='prepared')
        with self.assertRaises(OperatorError):self.proof()

    def test_stored_authorization_is_rechecked_not_cached(self):
        self.proof();self.native.store._authorize_plan.side_effect=OperatorError('revoked')
        with self.assertRaisesRegex(OperatorError,'revoked'):self.proof()

    def test_plan_identity_and_native_artifact_mismatch_refused(self):
        original=copy.deepcopy(self.bundle)
        for key,value in [('operation_id',ident(501)),('operation_type','install'),('deployment_id',ident(502)),
                ('site_ids',[ident(21)]),('base_release_digest','wrong'),('target_release_digest','wrong'),
                ('artifacts',[]),('artifacts',[dict(runtime='native')])]:
            self.bundle=copy.deepcopy(original);self.bundle['plan'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(OperatorError):self.proof()

    def test_active_partial_duplicate_and_foreign_scope_refused(self):
        original=copy.deepcopy(self.f.site);targets=copy.deepcopy(self.lock['targets'])
        for case in ['active','extra_scope','duplicate','no_target','wrong_target']:
            self.f.site=copy.deepcopy(original);self.lock['targets']=copy.deepcopy(targets)
            if case=='active':self.f.site['features'][1]['feature_state']='enabled'
            elif case=='extra_scope':self.f.site['features'].append(dict(self.f.site['features'][1],workspace_id=ident(31)))
            elif case=='duplicate':self.f.site['features'].append(copy.deepcopy(self.f.site['features'][1]))
            elif case=='no_target':self.lock['targets']=[]
            else:self.lock['targets'][0]['site_id']=ident(21)
            with self.subTest(case=case),self.assertRaises(OperatorError):self.proof()

    def test_target_image_contract_code_and_version_refused(self):
        original=copy.deepcopy(self.new)
        for case in ['image','contract','code','version','manifest_pin']:
            self.new.clear();self.new.update(copy.deepcopy(original))
            if case=='image':self.reader.config['runtime']['image']='modular-document-stats@sha256:'+'6'*64
            elif case=='contract':self.new['manifest']['external_service']['endpoint_config']='foreign'
            elif case=='code':self.new['inventory']['backend/evil.py']='0'*64
            elif case=='version':self.new['manifest']['plugin']['version']='0.0.0'
            else:self.new['manifest']['plugin']['description']='changed'
            with self.subTest(case=case),self.assertRaises(OperatorError):self.proof()
            self.reader.config['runtime']['image']=self.image

    def test_current_endpoint_health_and_image_must_match_review(self):
        original=copy.deepcopy(self.f.external_state)
        for case in ['revoked','generation','destination','duplicate','health','health_image']:
            self.f.external_state=copy.deepcopy(original);e=self.f.external_state['endpoints'][0]
            if case=='revoked':e['state']='revoked'
            elif case=='generation':e['generation']+=1
            elif case=='destination':e['destination']='http://foreign:8080'
            elif case=='duplicate':self.f.external_state['endpoints'].append(copy.deepcopy(e))
            elif case=='health':next(iter(self.f.external_state['service_health'].values()))['state']='unavailable'
            else:next(iter(self.f.external_state['service_health'].values()))['expected_image_digest']='sha256:'+'6'*64
            with self.subTest(case=case),self.assertRaises(OperatorError):self.proof()

    def test_recovery_preserves_later_revocations_rotation_but_not_destination_or_image(self):
        self.native.store.status.return_value=dict(state='recovery_required')
        self.f.endpoint.update(state='revoked',generation=self.f.endpoint['generation']+1,public_key_ref='rotated_public')
        self.f.external_state['service_health']={}
        self.proof(recovery=True)
        for key,value in [('destination','http://foreign:8080'),('expected_image_digest','sha256:'+'6'*64),('generation',0)]:
            old=self.f.endpoint[key];self.f.endpoint[key]=value
            with self.subTest(key=key),self.assertRaises(OperatorError):self.proof(recovery=True)
            self.f.endpoint[key]=old

    def dbcheck(self,value,*,features=None):
        cr=Mock();cr.fetchall.side_effect=[[(101,self.row['installation_id'],self.row['plugin_id'],self.row['version'],self.row['digest'],self.row['metadata_state'],self.row['manifest'])],
            features if features is not None else [(ident(30),'suspended',self.row['plugin_id'])]]
        return _reference(cr,LifecycleScope(self.f.site['site_id'],data_digest(self.old),reference=value))

    def test_native_child_rechecks_exact_old_metadata_and_full_suspended_scope(self):
        value=self.policy();self.assertEqual(self.dbcheck(value),data_digest(value))
        for features in [[(ident(30),'enabled',self.row['plugin_id'])],[],[(ident(31),'suspended',self.row['plugin_id'])]]:
            with self.subTest(features=features),self.assertRaises(DispatchLifecycleError):self.dbcheck(value,features=features)
        self.row['manifest']['plugin']['description']='changed'
        with self.assertRaises(DispatchLifecycleError):self.dbcheck(value)

    def test_native_default_and_unneeded_or_malformed_proof_refused(self):
        value=self.policy();normal=copy.deepcopy(value);normal.pop('worker_transition');normal['profile']='r1-reference-stateless-v1'
        with self.assertRaises(DispatchLifecycleError):self.dbcheck(normal)
        for key,val in [('operation_id','bad'),('plan_hash','bad'),('target_image',value['worker_transition']['base_image']),('workspaces',[])]:
            bad=copy.deepcopy(value);bad['worker_transition'][key]=val
            with self.subTest(key=key),self.assertRaises(DispatchLifecycleError):self.dbcheck(bad)
        self.row['manifest']['external_service']['expected_image']=self.image
        with self.assertRaisesRegex(DispatchLifecycleError,'metadata changed|Unused'):self.dbcheck(value)


if __name__=='__main__':unittest.main()
