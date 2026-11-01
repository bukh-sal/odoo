"""Actual existing native identity/metadata tables; all fixture writes roll back."""
import copy,json,unittest
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import dispatch_lifecycle as LC

class ExternalAuthorityTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.release=self.cr.fetchone()[0]
        self.lifecycle=LC.LifecycleScope(FIXTURE['site_id'],self.release);self.before=LC.observe(self.cr,self.lifecycle)
        self.original={}
        for table in ['mp_plugin_installation','mp_service_binding','mp_plugin_grant','mp_workspace_plugin','mp_workspace','mp_membership','mp_example_note']:
            self.cr.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id');self.original[table]=self.cr.fetchall()
        consumer=ENV['mp.plugin.installation'].search([('plugin_id','=','org.example.notes')]);self.assertEqual(len(consumer),1)
        manifest=copy.deepcopy(consumer.manifest)
        manifest['services']['requires'].append(dict(alias='stats',id='org.example.document_stats.analysis',contract_major=1,version='>=1.0,<2.0'))
        consumer.write({'manifest':manifest})
        provider_manifest=copy.deepcopy(PROVIDER);provider_manifest['external_service']['expected_image']=IMAGE
        provider_manifest['permissions']['defines']={'analysis.run':'Analyze supplied document text'}
        self.provider=ENV['mp.plugin.installation'].create(dict(public_id=str(uuid4()),plugin_id='org.example.document_stats',version=provider_manifest['plugin']['version'],artifact_digest='sha256:'+'a'*64,runtime='external_service',state='installed',manifest=provider_manifest))
        workspace=FIXTURE['workspaces']['C']
        self.feature=ENV['mp.workspace.plugin'].create(dict(workspace_id=workspace['id'],plugin_id=self.provider.plugin_id,installation_id=self.provider.id,availability='enabled'))
        self.grant=ENV['mp.plugin.grant'].create(dict(installation_id=consumer.id,workspace_id=workspace['id'],capability='org.example.document_stats:analysis.run',state='approved'))
        binding=copy.deepcopy(FIXTURE['bindings']['C']);binding.update(binding_id=str(uuid4()),alias='stats',service_id='org.example.document_stats.analysis',provider_plugin_id=self.provider.plugin_id,provider_installation_id=self.provider.public_id,api_version='1.0',contract_major=1)
        self.binding=ENV['mp.service.binding'].create(dict(public_id=binding['binding_id'],workspace_id=workspace['id'],consumer_id=consumer.id,alias='stats',descriptor=binding,state='active'))
        self.endpoint=copy.deepcopy(ENDPOINT);self.endpoint.update(site_id=FIXTURE['site_id'],workspace_id=workspace['public_id'],installation_id=self.provider.public_id,expected_image_digest=IMAGE.split('@')[1])
        self.native=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),workspace['public_id'])
        frame=CallFrame(FIXTURE['users']['alice']['principal_id'],workspace['public_id'],FIXTURE['site_id'],consumer.public_id,'org.example.notes',())
        self.native=self.native(context={**self.native.context,'_mp_call_frame':frame})
    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(LC.observe(self.cr,self.lifecycle),self.before)
        for table,rows in self.original.items():
            self.cr.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id');self.assertEqual(self.cr.fetchall(),rows)
        self.cr.rollback()
    def authorize(self,endpoint=None):return authorize_analysis(self.native,'stats',endpoint or self.endpoint)
    def denied(self,fn=None):
        # No surrounding flushing savepoint: pending native policy is the case.
        with self.assertRaises((AccessError,PublicError)):(fn or self.authorize)()
    def test_current_original_actor_binding_grant_and_endpoint_positive(self):
        value=self.authorize();self.assertEqual(value.binding,self.binding.descriptor);self.assertEqual(value.endpoint,self.endpoint)
        self.assertEqual(value.spec.permission,'org.example.document_stats:analysis.run')
    def test_pending_grant_revocation_denies_without_manual_flush(self):
        self.grant.write({'state':'revoked'});self.denied()
    def test_pending_provider_suspension_denies(self):
        self.provider.write({'state':'suspended'});self.denied()
    def test_pending_binding_unavailability_denies(self):
        self.binding.write({'state':'unavailable'});self.denied()
    def test_pending_feature_suspension_denies(self):
        self.feature.write({'availability':'suspended'});self.denied()
    def test_pending_membership_revocation_denies(self):
        scope=self.native.context['_mp_scope'];membership=ENV['mp.membership'].search([('principal_id','=',scope.principal_id),('workspace_id','=',scope.workspace_id)])
        membership.write({'state':'revoked'});self.denied()
    def test_foreign_endpoint_image_or_state_denied(self):
        for field,value in [('workspace_id',FIXTURE['workspaces']['B']['public_id']),('installation_id',str(uuid4())),('site_id',str(uuid4())),('expected_image_digest','sha256:'+'b'*64),('state','suspended')]:
            self.denied(lambda:self.authorize({**self.endpoint,field:value}))
    def test_forged_backing_actor_cannot_reuse_current_frame(self):
        wrong=api.Environment(self.cr,FIXTURE['users']['bob']['id'],self.native.context)
        self.denied(lambda:authorize_analysis(wrong,'stats',self.endpoint))
