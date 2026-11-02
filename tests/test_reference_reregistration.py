"""Actual reference-policy boundary; independent IO substituted, guard is real."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_external_projection as fixtures
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.operator_os import OperatorError


class ReferenceReregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ExternalProjection.setUpClass()

    def setUp(self):
        self.f=fixtures.ExternalProjection();self.f.setUp()
        self.f.config['project']='mp-disposable-reference-unit'
        self.f.site['installations'][1]['metadata_state']='removed'
        self.f.site['features'][1]['feature_state']='suspended'
        self.native=Mock();self.native.config=self.f.config;self.native.target_path=Path('private/target.json')
        self.worker=dict(runtime=dict(image=self.f.external['manifest']['external_service']['expected_image']))
        self.reader=Mock();self.reader.target=self.f.config;self.reader.config=self.worker
        self.reader.publisher._document.return_value=dict(generation=5,endpoints=[])
        self.reader.planning_state.side_effect=lambda:copy.deepcopy(self.f.external_state)

    def policy(self):
        with patch('modular_platform.reference_dispatch.WorkerPlanningReader',return_value=self.reader),\
                patch('modular_platform.reference_dispatch.read_metadata',return_value=self.f.site),\
                patch('modular_platform.reference_dispatch.Catalog') as catalog,\
                patch('modular_platform.reference_dispatch.private_json',side_effect=lambda p:self.worker if p.name=='worker-target.json' else self.f.config):
            catalog.return_value.snapshot.return_value=self.f.catalog
            return ReferenceDispatchMaintenance(self.native).reference_policy(self.f.config)

    def test_approved_endpoint_before_reregistration_is_inert_even_when_worker_down(self):
        next(iter(self.f.external_state['service_health'].values()))['state']='unavailable'
        before=copy.deepcopy(self.f.site);result=self.policy()
        self.assertEqual(result['registrations'][0]['state'],'removed')
        self.assertEqual(result['registrations'][0]['features'][0]['feature_state'],'suspended')
        self.assertEqual(self.f.site,before)
        projected=self.f.project()['state'];self.assertEqual(projected['endpoints'],[])
        self.assertEqual(projected['installations'][1]['state'],'not_installed')

    def test_absent_and_revoked_approvals_remain_inert(self):
        self.f.endpoint['state']='revoked';self.policy()
        self.f.external_state['endpoints']=[];self.policy()

    def test_removed_feature_or_approved_grant_cannot_be_revived(self):
        self.f.site['features'][1]['feature_state']='enabled'
        with self.assertRaisesRegex(OperatorError,'active availability'):self.policy()
        self.f.site['features'][1]['feature_state']='suspended'
        self.f.site['grants']=[dict(installation_id=self.f.endpoint['installation_id'],state='approved')]
        with self.assertRaisesRegex(OperatorError,'approved grants'):self.policy()

    def test_active_provider_and_consumer_bindings_are_refused(self):
        ident=self.f.endpoint['installation_id']
        for role in ['consumer_installation_id','provider_installation_id']:
            d=dict(consumer_installation_id='other',provider_installation_id='other');d[role]=ident
            self.f.site['bindings']=[dict(descriptor=d,state='active')]
            with self.subTest(role=role),self.assertRaisesRegex(OperatorError,'active binding'):self.policy()
        self.f.site['bindings'][0]['state']='removed';self.policy()

    def test_enabled_preregistration_requires_exact_site_and_both_image_pins(self):
        endpoint=copy.deepcopy(self.f.endpoint);image=self.worker['runtime']['image']
        for case in ['site','endpoint_image','runtime_image','suspended','duplicate']:
            self.f.external_state['endpoints']=[copy.deepcopy(endpoint)];self.worker['runtime']['image']=image
            e=self.f.external_state['endpoints'][0]
            if case=='site':e['site_id']='foreign'
            elif case=='endpoint_image':e['expected_image_digest']='sha256:'+'0'*64
            elif case=='runtime_image':self.worker['runtime']['image']='modular-document-stats@sha256:'+'0'*64
            elif case=='suspended':e['state']='suspended'
            else:self.f.external_state['endpoints'].append(copy.deepcopy(e))
            with self.subTest(case=case),self.assertRaisesRegex(OperatorError,'pre-registration'):self.policy()

    def test_installed_scope_still_requires_endpoint_and_matching_image(self):
        self.f.site['installations'][1]['metadata_state']='installed';self.policy()
        self.f.external_state['endpoints']=[]
        with self.assertRaisesRegex(OperatorError,'Installed reference scope'):self.policy()


if __name__=='__main__':unittest.main()
