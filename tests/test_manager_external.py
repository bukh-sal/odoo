"""Manager metadata proposals use the ordinary planner and independent review."""
import ast,copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_external_planning as fixtures
from test_plans import ident,STAMP
from modular_platform.contracts import ContractError
from modular_platform.manager_planning import manager_runtime,prepare_manager_external
from modular_platform.resolution import PlanningError
from modular_platform.operator_os import OperatorError
from modular_platform.manager_views import installed_view

class ManagerExternal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ExternalPlanning.setUpClass()

    def setUp(self):
        self.f=fixtures.ExternalPlanning();self.f.setUp()
        self.nomination=dict(schema_version=1,operation='prepare',operation_type='suspend',
            plugin_id=self.f.target['plugin_id'],site_id=ident(20),workspace_ids=[ident(30)],cascade=False)

    def prepare(self):
        return prepare_manager_external(self.f.document,[self.f.f.site],self.f.f.catalog,self.f.f.external_state,
            self.nomination,operation_id=ident(500),created_at=STAMP)

    def select(self,action,descriptor=None):
        self.nomination['operation_type']=action
        if action in ('install','upgrade'):
            descriptor=descriptor or self.f.f.external
            self.nomination.update(artifact_version=descriptor['manifest']['plugin']['version'],artifact_digest=descriptor['digest'])

    def test_suspended_registration_without_staging_reconstructs_and_does_not_mutate(self):
        self.f.unregistered();self.select('install')
        before=copy.deepcopy((self.f.document,self.f.f.site,self.f.f.external_state))
        bundle=self.prepare()
        self.assertEqual(bundle,self.f.prepare('install'))
        self.assertEqual(self.f.independent()(bundle),self.f.document['state'])
        self.assertEqual((self.f.document,self.f.f.site,self.f.f.external_state),before)
        self.assertTrue(bundle['display']['restart_required'])
        self.assertFalse(bundle['display']['native_code_requires_trust'])
        self.assertNotIn('staged_image',bundle['operation_lock'])

    def test_registration_during_outage_never_activates(self):
        self.f.unregistered();self.select('install')
        next(iter(self.f.f.external_state['service_health'].values()))['state']='unavailable'
        bundle=self.prepare()
        self.assertEqual(bundle['operation_lock']['feature_states'][0]['availability'],'suspended')
        self.assertEqual(self.f.independent()(bundle),self.f.document['state'])

    def test_enable_requires_current_health_and_independent_endpoint_reader(self):
        self.select('enable');bundle=self.prepare()
        self.assertEqual(self.f.independent()(bundle),self.f.document['state'])
        next(iter(self.f.f.external_state['service_health'].values()))['state']='unavailable'
        with self.assertRaises(PlanningError):self.prepare()
        with self.assertRaises((OperatorError,PlanningError)):self.f.independent()(bundle)

    def test_upgrade_is_exact_and_retains_feature_state_and_native_roots(self):
        candidate=copy.deepcopy(self.f.f.external);candidate['manifest']['plugin']['version']='0.1.2';candidate['digest']='sha256:'+'c'*64
        self.f.f.catalog.append(candidate);self.f.document=self.f.f.project();self.select('upgrade',candidate)
        bundle=self.prepare()
        self.assertEqual(bundle,self.f.prepare('upgrade',selections=[dict(plugin_id=self.f.target['plugin_id'],version='0.1.2',digest=candidate['digest'])]))
        self.assertNotIn('feature_states',bundle['operation_lock'])
        self.assertEqual(self.f.independent()(bundle),self.f.document['state'])

    def test_unregister_requires_revocation_and_includes_site_scopes(self):
        self.select('unregister');self.nomination['workspace_ids']=[]
        with self.assertRaisesRegex(PlanningError,'Revoke'):self.prepare()
        self.f.f.endpoint['state']='revoked';bundle=self.prepare()
        self.assertEqual(bundle,self.f.prepare('unregister'))
        self.assertTrue(bundle['display']['restart_required'])
        self.assertEqual(self.f.independent()(bundle),self.f.document['state'])

    def test_required_consumer_blocks_unregister_instead_of_silent_cascade(self):
        self.f.consumer(optional=False);self.f.f.endpoint['state']='revoked'
        self.select('unregister');self.nomination.update(workspace_ids=[],cascade=True)
        with self.assertRaises(PlanningError):self.prepare()

    def test_unknown_scope_site_and_exact_artifact_tampering_fail(self):
        for fields in [dict(site_id=ident(99)),dict(workspace_ids=[ident(99)])]:
            original=self.nomination;self.nomination=original|fields
            with self.assertRaises(PlanningError):self.prepare()
            self.nomination=original
        self.select('upgrade');self.nomination['artifact_digest']='sha256:'+'f'*64
        with self.assertRaises(PlanningError):self.prepare()

    def test_same_version_or_downgrade_cannot_be_called_upgrade(self):
        self.select('upgrade')
        with self.assertRaisesRegex(PlanningError,'strictly newer'):self.prepare()
        candidate=copy.deepcopy(self.f.f.external);candidate['manifest']['plugin']['version']='0.1.0';candidate['digest']='sha256:'+'b'*64
        self.f.f.catalog.append(candidate);self.select('upgrade',candidate)
        with self.assertRaisesRegex(PlanningError,'strictly newer'):self.prepare()

    def test_runtime_cannot_be_supplied_by_browser_and_native_ops_reject_external(self):
        self.assertEqual(manager_runtime(self.f.document,self.f.f.catalog,self.nomination),'external_service')
        for action in ('uninstall','remove'):
            self.nomination.update(operation_type=action,workspace_ids=[])
            if action=='remove':self.nomination['artifact_digest']=self.f.f.external['digest']
            with self.assertRaises(PlanningError):self.prepare()
        self.nomination.pop('artifact_digest',None);self.nomination.update(operation_type='suspend',workspace_ids=[ident(30)],runtime='native')
        with self.assertRaises(ContractError):self.prepare()

    def test_native_nomination_remains_native(self):
        self.nomination.update(plugin_id='org.test.a')
        self.assertEqual(manager_runtime(self.f.document,self.f.f.catalog,self.nomination),'native')
        with self.assertRaises(PlanningError):self.prepare()

    def test_closed_scope_can_suspend_but_cannot_enable(self):
        self.f.f.site['workspaces'][0]['state']='closed'
        self.assertEqual(self.prepare()['plan']['operation_type'],'suspend')
        self.select('enable')
        with self.assertRaises(PlanningError):self.prepare()

    def test_actual_controller_routes_external_before_native_staging(self):
        tree=ast.parse((ROOT/'platform_addons/mp_core/operations.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Operations')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='prepare');method.decorator_list=[]
        cursor=Mock();cursor.fetchone.return_value=(0,)
        save=Mock(side_effect=lambda bundle,*_:bundle)
        native=Mock(side_effect=AssertionError('External request reached native planner'))
        profile=dict(catalog=self.f.f.catalog,external_state=self.f.f.external_state)
        ns=dict(request=SimpleNamespace(env=SimpleNamespace(cr=cursor)),operator=lambda:(6,'actor'),bounded_body=lambda _:self.nomination,
            site_id=lambda:ident(20),result=lambda run:run(),profile_document=lambda:(self.f.document,profile,self.f.f.site),
            manager_runtime=manager_runtime,prepare_manager_external=prepare_manager_external,prepare_manager_native=native,
            uuid4=lambda:ident(500),stamp=lambda:STAMP,_save_prepared=save,AccessError=PermissionError,PublicError=ValueError)
        exec(compile(ast.Module(body=[method],type_ignores=[]),'actual-manager-prepare','exec'),ns)
        self.assertEqual(ns['prepare'](None),self.prepare());native.assert_not_called();save.assert_called_once()

    def view(self,external=True):
        # Solver fixtures intentionally omit snapshot-only descriptor fields.
        catalog=copy.deepcopy(self.f.f.catalog)
        for descriptor in catalog:descriptor['version']=descriptor['manifest']['plugin']['version']
        profile=dict(catalog=catalog,observed_at=STAMP)
        if external:profile['external_state']=self.f.f.external_state
        return installed_view(profile,self.f.f.site,now=STAMP)['items']

    def external_row(self,external=True):
        return next(r for r in self.view(external) if r['runtime']=='external_service')

    def test_observed_health_is_separate_from_feature_availability(self):
        self.assertEqual(self.external_row()['health']['state'],'healthy')
        self.f.f.site['features'][1]['feature_state']='suspended'
        row=self.external_row();self.assertEqual(row['health']['state'],'healthy')
        self.assertEqual(row['features'][0]['availability'],'suspended')
        self.assertEqual(self.external_row(False)['health']['state'],'unknown')

    def test_outage_revocation_scope_and_image_mismatch_degrade(self):
        initial=copy.deepcopy(self.f.f.external_state)
        for kind in ['outage','revocation','scope','image']:
            self.f.f.external_state=copy.deepcopy(initial)
            if kind=='outage':next(iter(self.f.f.external_state['service_health'].values()))['state']='unavailable'
            elif kind=='revocation':self.f.f.external_state['endpoints'][0]['state']='revoked'
            elif kind=='scope':
                self.f.f.external_state['endpoints'][0]['workspace_id']=ident(31)
                health=self.f.f.external_state['service_health']
                health[ident(101)+':'+ident(31)]=health.pop(ident(101)+':'+ident(30))
            else:next(iter(self.f.f.external_state['service_health'].values()))['expected_image_digest']='sha256:'+'a'*64
            with self.subTest(kind=kind):self.assertEqual(self.external_row()['health']['state'],'degraded')

    def test_malformed_health_cannot_invent_an_approved_scope(self):
        self.f.f.external_state['endpoints'][0]['workspace_id']=ident(31)
        with self.assertRaises(PlanningError):self.external_row()

    def test_removed_metadata_does_not_report_runtime_stopped_or_healthy(self):
        self.f.f.site['installations'][1]['metadata_state']='removed'
        self.f.f.site['features'][1]['feature_state']='suspended'
        row=self.external_row();self.assertEqual(row['database_state'],'not_installed')
        self.assertEqual(row['health']['state'],'unknown');self.assertIn('separately managed',row['health']['reason'])

    def test_required_external_provider_does_not_need_fictitious_native_addon(self):
        self.f.consumer(optional=False)
        row=next(r for r in self.view() if r['runtime']=='native')
        self.assertEqual(row['dependencies']['state'],'satisfied')
        next(iter(self.f.f.external_state['service_health'].values()))['state']='unavailable'
        row=next(r for r in self.view() if r['runtime']=='native')
        self.assertEqual(row['dependencies']['state'],'unavailable');self.assertEqual(row['health']['state'],'degraded')

if __name__=='__main__':unittest.main()
