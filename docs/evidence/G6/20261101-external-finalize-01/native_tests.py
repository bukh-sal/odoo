"""Real native result gates with temporary authority files; all SQL rolls back."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from odoo.addons.mp_core import external_job as bridge
from odoo.addons.mp_example_notes_stats import jobs as connector

TABLES=['mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential',
    'mp_workspace','mp_membership','mp_principal','mp_audit_event','ir_config_parameter','ir_module_module',
    'mp_job','mp_dispatch_control','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption',
    'mp_event_consumer_state','mp_example_note']


def rows():
    result={}
    for table in TABLES:
        ENV.cr.execute("SELECT count(*),encode(sha256(convert_to(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'[]'),'UTF8')),'hex') FROM "+table+' t')
        result[table]=ENV.cr.fetchone()
    return result


class FinalizeTests(NotesAnalysisTests):
    def setUp(self):
        ENV.cr.rollback();self.all_before=rows();ENV.cr.rollback()
        super().setUp()
        self.cr.execute("SET LOCAL lock_timeout='2s'")
        manifest=copy.deepcopy(PROVIDER)
        self.provider=ENV['mp.plugin.installation'].create(dict(public_id=str(uuid4()),plugin_id='org.example.document_stats',
            version=manifest['plugin']['version'],artifact_digest='sha256:'+'d'*64,runtime='external_service',state='installed',manifest=manifest))
        self.external_feature=ENV['mp.workspace.plugin'].create(dict(workspace_id=self.workspace['id'],plugin_id=self.provider.plugin_id,
            installation_id=self.provider.id,availability='enabled'))
        self.external_grant=ENV['mp.plugin.grant'].create(dict(installation_id=self.connector.id,workspace_id=self.workspace['id'],
            capability='org.example.document_stats:analysis.run',state='approved'))
        binding=copy.deepcopy(FIXTURE['bindings']['C']);binding.update(binding_id=str(uuid4()),alias='stats',
            service_id='org.example.document_stats.analysis',consumer_installation_id=self.connector.public_id,
            provider_plugin_id=self.provider.plugin_id,provider_installation_id=self.provider.public_id,api_version='1.0',contract_major=1)
        self.stats_binding=ENV['mp.service.binding'].create(dict(public_id=binding['binding_id'],workspace_id=self.workspace['id'],
            consumer_id=self.connector.id,alias='stats',descriptor=binding,state='active'))
        self.endpoint=copy.deepcopy(ENDPOINT);self.endpoint.update(installation_id=self.provider.public_id,site_id=FIXTURE['site_id'],
            workspace_id=self.workspace['public_id'],expected_image_digest=manifest['external_service']['expected_image'].split('@')[1])
        temporary=tempfile.TemporaryDirectory(prefix='mp-final-apply-source-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);(self.root/'keys').mkdir()
        self.key_path=self.root/'keys'/(self.endpoint['public_key_ref']+'.pem');self.rotate_key()
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id'")
        self.publication=dict(schema_version=1,deployment_id=self.cr.fetchone()[0],site_id=FIXTURE['site_id'],generation=1,
            endpoints=[dict(descriptor=self.endpoint,addresses=['172.28.0.9'],key_id='source-test-key')])
        self.publish()
        real=bridge.authorization_snapshot
        self.snapshot=lambda provider_env:real(provider_env,authority_root=str(self.root))
        p=patch.object(connector,'authorization_snapshot',side_effect=self.snapshot);p.start();self.addCleanup(p.stop)

    def rotate_key(self):
        public=rsa.generate_private_key(public_exponent=65537,key_size=2048).public_key()
        self.key_path.write_bytes(public.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))

    def publish(self):
        (self.root/'authority.json').write_text(json.dumps(self.publication))

    def tearDown(self):
        super().tearDown();self.assertEqual(rows(),self.all_before);ENV.cr.rollback()

    def computed(self):
        _,_,digest=self.snapshot(self.native)
        return dict(statistics=dict(characters=17,words=3,lines=2),authority_digest=digest)

    def claim(self):
        self.start();invocation=jobs.prepare_one(ENV,str(uuid4()))
        self.assertIsInstance(invocation,jobs.Invocation)
        return invocation,self.computed()

    def finish_denied(self,change,code):
        invocation,computed=self.claim();change()
        result=jobs.finish_one(ENV,invocation,computed)
        self.assertEqual(result['error_code'],code)
        self.cr.execute('SELECT state,result,error_code FROM mp_job WHERE public_id=%s',[invocation.claim.job_id])
        self.assertEqual(self.cr.fetchone(),('dead_letter',None,code))

    def test_revision_snapshot_and_read_only_result_use_existing_job_guards(self):
        invocation,computed=self.claim()
        result=jobs.finish_one(ENV,invocation,computed)
        self.assertEqual(result,dict(note_id=self.note.public_id,revision=1,statistics=computed['statistics']))
        self.assertEqual(self.status()['result'],result)
        self.assertNotIn('authority_digest',result)
        self.assertEqual(self.note.revision,1);self.assertEqual(self.note.body,'hello world\nagain')

    def test_note_revision_change_before_finish_refuses_stale_statistics(self):
        self.finish_denied(lambda:self.note.with_context(expected_revision=1).write({'body':'changed'}),'CONFLICT')

    def test_provider_grant_revoked_after_compute_denies_result(self):
        self.finish_denied(lambda:self.external_grant.write({'state':'revoked'}),'FORBIDDEN')

    def test_provider_feature_suspended_after_compute_denies_result(self):
        self.finish_denied(lambda:self.external_feature.write({'availability':'suspended'}),'PLUGIN_SUSPENDED')

    def test_provider_unregistered_after_compute_denies_result(self):
        self.finish_denied(lambda:self.provider.write({'state':'removed'}),'PLUGIN_SUSPENDED')

    def test_binding_unavailable_after_compute_denies_result(self):
        self.finish_denied(lambda:self.stats_binding.write({'state':'unavailable'}),'DEPENDENCY_UNAVAILABLE')

    def test_equivalent_replaced_binding_cannot_reuse_old_authority_fingerprint(self):
        def replace():
            binding=dict(self.stats_binding.descriptor,binding_id=str(uuid4()))
            self.stats_binding.unlink()
            self.stats_binding=ENV['mp.service.binding'].create(dict(public_id=binding['binding_id'],descriptor=binding,
                workspace_id=self.workspace['id'],consumer_id=self.connector.id,alias='stats',state='active'))
        self.finish_denied(replace,'FORBIDDEN')

    def test_endpoint_revoked_after_compute_denies_result(self):
        def revoke():self.endpoint['state']='revoked';self.publication['generation']+=1;self.publish()
        self.finish_denied(revoke,'DEPENDENCY_UNAVAILABLE')

    def test_publication_generation_change_after_compute_requires_new_result(self):
        def change():self.publication['generation']+=1;self.publish()
        self.finish_denied(change,'FORBIDDEN')

    def test_public_key_rotation_after_compute_denies_old_result(self):
        self.finish_denied(self.rotate_key,'FORBIDDEN')

    def test_egress_change_after_compute_denies_old_result(self):
        def change():self.publication['endpoints'][0]['addresses']=['172.28.0.10'];self.publish()
        self.finish_denied(change,'FORBIDDEN')

    def test_publication_changed_during_native_authorization_denies_result(self):
        invocation,computed=self.claim();real=bridge.authorize_analysis
        def change(*args):
            result=real(*args);self.publication['generation']+=1;self.publish();return result
        with patch.object(bridge,'authorize_analysis',side_effect=change):result=jobs.finish_one(ENV,invocation,computed)
        self.assertEqual(result['error_code'],'FORBIDDEN')

    def test_old_statistics_only_computed_shape_is_not_accepted(self):
        invocation,computed=self.claim();result=jobs.finish_one(ENV,invocation,computed['statistics'])
        self.assertEqual(result['error_code'],'VALIDATION_FAILED')

    def test_completed_status_survives_worker_revocation_without_issuer_or_remote_io(self):
        invocation,computed=self.claim();result=jobs.finish_one(ENV,invocation,computed)
        self.endpoint['state']='revoked';self.publish();self.key_path.unlink()
        self.assertEqual(self.status()['result'],result)

    def test_original_actor_revoked_after_compute_denies_result(self):
        def revoke():
            scope=self.native.context['_mp_scope']
            ENV['mp.membership'].search([('principal_id','=',scope.principal_id),('workspace_id','=',scope.workspace_id)]).write({'state':'revoked'})
        self.finish_denied(revoke,'FORBIDDEN')

    def test_compute_wrapper_keeps_fingerprint_private_and_sends_only_worker_input(self):
        invocation,expected=self.claim();authority,snapshot,digest=self.snapshot(self.native)
        class Client:
            def __init__(inner,current,*args,**kwargs):inner.current=current
            def analyze(inner,values,**kwargs):
                self.assertEqual(values,invocation.prepared['input']);self.assertNotIn('authority_digest',values)
                inner.current();inner.current();return dict(data=expected['statistics'])
        with patch.object(bridge,'_snapshot',return_value=(authority,snapshot,digest)),patch.object(bridge,'WorkerClient',Client):
            self.assertEqual(jobs.compute(invocation),expected)

    def test_changed_binding_fingerprint_around_compute_denies_same_endpoint(self):
        invocation,expected=self.claim();authority,snapshot,digest=self.snapshot(self.native)
        class Client:
            def __init__(inner,current,*args,**kwargs):inner.current=current
            def analyze(inner,*args,**kwargs):inner.current()
        with patch.object(bridge,'_snapshot',side_effect=[(authority,snapshot,digest),(authority,snapshot,'sha256:'+'f'*64)]),patch.object(bridge,'WorkerClient',Client):
            with self.assertRaises(bridge.WorkerDispatchError):jobs.compute(invocation)
