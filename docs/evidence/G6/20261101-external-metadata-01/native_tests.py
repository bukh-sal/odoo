"""Real PostgreSQL source tests; every candidate mutation rolls back."""
import copy,unittest
from uuid import uuid4
from modular_platform.metadata_sql import METADATA_SELECT
from modular_platform.plans import data_digest
from modular_platform.projection import project_deployment
from modular_platform.external_planning import prepare_external_metadata
from psycopg2.extras import Json


TABLES=['mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential',
    'mp_workspace','mp_membership','mp_principal','mp_audit_event','ir_config_parameter','ir_module_module',
    'mp_job','mp_dispatch_control','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption',
    'mp_event_consumer_state','mp_example_note']

def snapshot():
    with CONNECTION.cursor() as cr:
        result={}
        for table in TABLES:
            cr.execute("SELECT count(*),encode(sha256(convert_to(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'[]'),'UTF8')),'hex') FROM "+table+' t')
            result[table]=cr.fetchone()
        return result


class ExternalMetadataTests(unittest.TestCase):
    def setUp(self):
        CONNECTION.rollback();self.before=snapshot();CONNECTION.rollback();self.cr=CONNECTION.cursor()
        self.config=copy.deepcopy(CONFIG);self.external=copy.deepcopy(EXTERNAL)
        self.target=copy.deepcopy(TARGET);self.catalog=copy.deepcopy(CATALOG)
        self.cr.execute("UPDATE mp_dispatch_control SET state='paused' WHERE site_id=%s",[CONFIG['sites'][0]['site_id']])

    def tearDown(self):
        CONNECTION.rollback();self.cr.close();self.assertEqual(snapshot(),self.before);CONNECTION.rollback()

    def site(self):self.cr.execute(METADATA_SELECT);return self.cr.fetchone()[0]

    def payload(self,action,*,activate=False):
        site=self.site();target={**self.target,'action':action}
        document=project_deployment(self.config,dict(runtime=RUNTIME,image_id=self.config['image_id'],sites=[site],external_state=self.external),self.catalog)
        selections=[];features=[]
        if action in ('install','upgrade'):
            candidate=next(r for r in reversed(self.catalog) if r['manifest']['plugin']['id']==self.target['plugin_id'])
            selections=[dict(plugin_id=self.target['plugin_id'],version=candidate['manifest']['plugin']['version'],digest=candidate['digest'])]
        if action=='install':features=[{k:target[k] for k in ['installation_id','site_id','workspace_id']}|dict(availability='enabled' if activate else 'suspended')]
        bundle=prepare_external_metadata(document,[site],self.catalog,targets=[target],operation_type=action,external_state=self.external,
            selections=selections,feature_states=features,operation_id=str(uuid4()),created_at='2026-11-01T06:10:00Z')
        selected={r['plugin_id']:r['digest'] for r in bundle['operation_lock']['release']['plugins']}
        plugins={r['manifest']['plugin']['id']:r for r in self.catalog if selected.get(r['manifest']['plugin']['id'])==r['digest']}
        return dict(bundle=bundle,base_state=document['state'],metadata_digest=data_digest(site),plugins=plugins,
            site_id=site['site_id'],deployment_id=self.config['deployment_id'],database=DATABASE,inventory_digest=RUNTIME['inventory_digest'])

    def apply(self,action,**kwargs):
        payload=self.payload(action,**kwargs);value=APPLY(self.cr,payload)
        self.config.update(published_release=payload['bundle']['operation_lock']['release'],generation=payload['bundle']['operation_lock']['release']['generation'],
            release_created_at=payload['bundle']['operation_lock']['release']['created_at'])
        self.cr.execute('UPDATE mp_dispatch_control SET release_digest=%s',[payload['bundle']['plan']['target_release_digest']])
        return payload,value

    def row(self):
        self.cr.execute('SELECT runtime,state,version,artifact_digest FROM mp_plugin_installation WHERE public_id=%s',[self.target['installation_id']]);return self.cr.fetchone()

    def test_register_enable_suspend_without_native_schema_or_runtime(self):
        modules=copy.deepcopy(self.site()['native_modules']);payload,result=self.apply('install')
        self.assertEqual(self.row()[:2],('external_service','installed'));self.assertFalse(result['native_maintenance']);self.assertFalse(result['runtime_control'])
        self.assertEqual(self.site()['native_modules'],modules)
        self.assertEqual(next(f for f in self.site()['features'] if f['installation_id']==self.target['installation_id'])['feature_state'],'suspended')
        self.apply('enable');self.assertEqual(next(f for f in self.site()['features'] if f['installation_id']==self.target['installation_id'])['feature_state'],'enabled')
        self.apply('suspend');self.assertEqual(next(f for f in self.site()['features'] if f['installation_id']==self.target['installation_id'])['feature_state'],'suspended')

    def test_unregister_preserves_tombstone_and_release(self):
        self.apply('install');release=self.site()['release_digest'];self.external['endpoints'][0].update(state='revoked',generation=2)
        self.apply('unregister');self.assertEqual(self.row()[:2],('external_service','removed'))
        self.assertEqual(self.site()['release_digest'],release)
        self.assertEqual(next(f for f in self.site()['features'] if f['installation_id']==self.target['installation_id'])['feature_state'],'suspended')

    def test_reregister_uses_same_identity_and_explicit_state(self):
        self.apply('install');self.external['endpoints'][0].update(state='revoked',generation=2);self.apply('unregister')
        self.external['endpoints'][0].update(state='enabled',generation=3);self.apply('install',activate=True)
        self.assertEqual(self.row()[:2],('external_service','installed'))
        self.assertEqual(len([i for i in self.site()['installations'] if i['plugin_id']==self.target['plugin_id']]),1)

    def test_metadata_upgrade_preserves_scope_availability(self):
        self.apply('install');candidate=copy.deepcopy(self.catalog[-1]);candidate['manifest']['plugin']['version']='0.1.1';candidate['digest']='sha256:'+'e'*64
        self.catalog.append(candidate);self.apply('upgrade');self.assertEqual(self.row()[2:4],('0.1.1',candidate['digest']))
        self.assertEqual(next(f for f in self.site()['features'] if f['installation_id']==self.target['installation_id'])['feature_state'],'suspended')

    def test_dispatch_must_be_paused_even_for_suspended_registration(self):
        data=self.payload('install');self.cr.execute("UPDATE mp_dispatch_control SET state='enabled'")
        with self.assertRaisesRegex(ValueError,'paused dispatch'):APPLY(self.cr,data)
        self.assertIsNone(self.row())

    def test_uncertain_job_keeps_metadata_absent(self):
        data=self.payload('install');self.cr.execute("UPDATE mp_job SET state='outcome_unknown' WHERE id=(SELECT min(id) FROM mp_job)")
        with self.assertRaisesRegex(ValueError,'Unreconciled dispatch'):APPLY(self.cr,data)
        self.assertIsNone(self.row())

    def test_stale_metadata_refused(self):
        data=self.payload('install');self.cr.execute('UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE public_id=%s',[self.target['workspace_id']])
        with self.assertRaisesRegex(ValueError,'preimage changed'):APPLY(self.cr,data)
        self.assertIsNone(self.row())

    def test_wrong_database_deployment_and_inventory_refused(self):
        for field,value in [('database','mp_disposable_r0_r1_wrong'),('deployment_id',str(uuid4())),('inventory_digest','sha256:'+'a'*64)]:
            data=self.payload('install');data[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):APPLY(self.cr,data)
        self.assertIsNone(self.row())

    def test_changed_artifact_refused_before_registration(self):
        data=self.payload('install');data['plugins'][self.target['plugin_id']]['manifest']['plugin']['description']='Unselected manifest'
        with self.assertRaisesRegex(ValueError,'selected trusted package'):APPLY(self.cr,data)
        self.assertIsNone(self.row())

    def test_same_child_payload_cannot_replay(self):
        data=self.payload('install');APPLY(self.cr,data)
        with self.assertRaisesRegex(ValueError,'preimage changed'):APPLY(self.cr,data)

    def test_late_python_fault_rolls_back_actual_postgresql_metadata_writes(self):
        data=self.payload('install');cursor=self.cr
        class FaultCursor:
            def execute(self,query,parameters=None):
                if 'INSERT INTO mp_audit_event' in query:raise RuntimeError('late metadata fixture fault')
                return cursor.execute(query,parameters)
            def __getattr__(self,name):return getattr(cursor,name)
        with self.assertRaisesRegex(RuntimeError,'late metadata fixture fault'):
            with CONNECTION:APPLY(FaultCursor(),data)
        self.assertEqual(snapshot(),self.before)

    def test_unregister_removes_only_owned_optional_fixture_binding(self):
        self.apply('install');site=self.site();native=copy.deepcopy(site['bindings'])
        consumer=next(i for i in site['installations'] if i['plugin_id']=='org.example.notes')
        binding=dict(schema_version=1,binding_id=str(uuid4()),site_id=self.target['site_id'],workspace_id=self.target['workspace_id'],
            consumer_installation_id=consumer['installation_id'],alias='metadata_source_fixture',service_id='org.example.document_stats.analysis',
            contract_major=1,api_version='1.0',provider_plugin_id=self.target['plugin_id'],provider_installation_id=self.target['installation_id'],generation=1,optional=True)
        self.cr.execute('SELECT id FROM mp_workspace WHERE public_id=%s',[self.target['workspace_id']]);workspace=self.cr.fetchone()[0]
        self.cr.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s',[consumer['installation_id']]);consumer_id=self.cr.fetchone()[0]
        self.cr.execute("INSERT INTO mp_service_binding(public_id,workspace_id,consumer_id,alias,descriptor,state) VALUES(%s,%s,%s,%s,%s,'active')",
            [binding['binding_id'],workspace,consumer_id,binding['alias'],Json(binding)])
        self.external['endpoints'][0].update(state='revoked',generation=2);self.apply('unregister')
        self.assertEqual(self.site()['bindings'],native)

    def test_unregister_revokes_exact_owned_grant_and_technical_credential(self):
        self.apply('install')
        self.cr.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s',[self.target['installation_id']]);installation=self.cr.fetchone()[0]
        self.cr.execute('SELECT id FROM mp_workspace WHERE public_id=%s',[self.target['workspace_id']]);workspace=self.cr.fetchone()[0]
        self.cr.execute("INSERT INTO mp_plugin_grant(installation_id,workspace_id,capability,state,policy_version) VALUES(%s,%s,%s,'approved',1)",
            [installation,workspace,'org.example.document_stats:analysis.run'])
        self.cr.execute("SELECT id FROM mp_principal WHERE kind='service' ORDER BY id LIMIT 1");principal=self.cr.fetchone()[0]
        self.cr.execute("""INSERT INTO mp_service_credential(name,principal_id,workspace_id,token_digest,installation_public_id,audience,actions,expires_at,state)
            VALUES('rollback fixture',%s,%s,%s,%s,'mp-host-v1','read',timezone('UTC',now())+interval '5 minutes','active') RETURNING id""",
            [principal,workspace,str(uuid4()),self.target['installation_id']]);credential=self.cr.fetchone()[0]
        self.external['endpoints'][0].update(state='revoked',generation=2);self.apply('unregister')
        self.cr.execute('SELECT state FROM mp_service_credential WHERE id=%s',[credential]);self.assertEqual(self.cr.fetchone(),('revoked',))
        self.cr.execute('SELECT state FROM mp_plugin_grant WHERE installation_id=%s',[installation]);self.assertEqual(self.cr.fetchall(),[('revoked',)])


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExternalMetadataTests))
CONNECTION.rollback()
print('MP_EXTERNAL_METADATA='+__import__('json').dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,
    errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures],original_rows_restored=True)))
raise SystemExit(0 if result.wasSuccessful() else 1)
