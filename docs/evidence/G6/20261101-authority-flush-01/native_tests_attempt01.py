"""Policy flush regressions on real native ORM/PG; every test rolls back."""
import hashlib,json,unittest
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4
from odoo import api,fields
from odoo.exceptions import AccessError
from odoo.addons.mp_identity import scopes
from odoo.addons.mp_core import job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import dispatch_lifecycle as LC


class PendingAuthorityTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.release=self.cr.fetchone()[0]
        self.scope=LC.LifecycleScope(FIXTURE['site_id'],self.release);self.baseline=LC.observe(self.cr,self.scope)
        self.cr.execute('SELECT role FROM mp_membership WHERE workspace_id=%s AND principal_id=(SELECT id FROM mp_principal WHERE public_id=%s)',[FIXTURE['workspaces']['C']['id'],FIXTURE['users']['alice']['principal_id']]);self.assertEqual(self.cr.fetchone()[0],'administrator')
        self.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']]);self.principal=ENV['mp.principal'].browse(self.cr.fetchone()[0])
        self.member=ENV['mp.membership'].search([('principal_id','=',self.principal.id),('workspace_id','=',FIXTURE['workspaces']['C']['id'])]);self.assertEqual(len(self.member),1)
        self.native=self.actor('alice','C')
        self.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);self.job=self.cr.fetchone()[0]
        self.assertEqual((self.job['state'],self.job['attempts']),('completed',2))
    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(LC.observe(self.cr,self.scope),self.baseline)
        self.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);self.assertEqual(self.cr.fetchone()[0],self.job);self.cr.rollback()
    def actor(self,user,workspace):
        native=scopes.scoped_environment(api.Environment(self.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id']);binding=FIXTURE['bindings'][workspace]
        frame=CallFrame(FIXTURE['users'][user]['principal_id'],FIXTURE['workspaces'][workspace]['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
        return native(context={**native.context,'_mp_call_frame':frame})
    def retry(self,native=None):return jobs.enqueue_bound(native or self.native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key'],request_id=str(uuid4()))
    def denied(self,fn):
        # Do not enter an Odoo flushing savepoint before the authorization:
        # doing so would hide exactly the pending-write case under test.
        with self.assertRaises((AccessError,PublicError)):fn()
    def test_completed_retry_original_result_trace_and_actor_are_unchanged(self):
        self.assertEqual(self.retry(),SEED['job_id']);self.assertEqual(jobs.status(self.native,SEED['job_id'])['result'],self.job['result'])
    def test_pending_role_downgrade_denies_saved_job_before_its_savepoint(self):
        self.member.write({'role':'viewer'});self.denied(self.retry)
        self.cr.execute('SELECT role FROM mp_membership WHERE id=%s',[self.member.id]);self.assertEqual(self.cr.fetchone()[0],'viewer')
    def test_pending_role_downgrade_denies_native_write_guard(self):
        self.member.write({'role':'viewer'});self.denied(lambda:self.native['mp.example.note'].browse([])._mp_guard('write'))
        self.assertEqual(scopes.current_scope(self.native).role,'viewer')
    def test_pending_membership_revocation_denies_scope_and_saved_status(self):
        self.member.write({'state':'revoked'});self.denied(lambda:scopes.current_scope(self.native));self.denied(lambda:jobs.status(self.native,SEED['job_id']))
    def test_pending_principal_suspension_denies_scope_and_retry(self):
        self.principal.write({'state':'suspended'});self.denied(lambda:scopes.current_scope(self.native));self.denied(self.retry)
    def test_pending_backing_user_deactivation_denies_scope(self):
        ENV['res.users'].browse(FIXTURE['users']['alice']['id']).write({'active':False});self.denied(lambda:scopes.current_scope(self.native))
    def test_pending_workspace_suspension_denies_native_read(self):
        ENV['mp.workspace'].browse(FIXTURE['workspaces']['C']['id']).write({'state':'suspended'});self.denied(lambda:self.native['mp.example.note'].browse([])._mp_guard('read'))
    def test_pending_feature_suspension_denies_native_read_and_job(self):
        feature=ENV['mp.workspace.plugin'].search([('workspace_id','=',FIXTURE['workspaces']['C']['id']),('plugin_id','=','org.example.notes')]);self.assertEqual(len(feature),1)
        feature.write({'availability':'suspended'});self.denied(lambda:self.native['mp.example.note'].browse([])._mp_guard('read'));self.denied(self.retry)
    def test_pending_policy_generation_is_in_new_scope_and_cache_key(self):
        workspace=ENV['mp.workspace'].browse(FIXTURE['workspaces']['C']['id']);old=workspace.policy_generation;workspace.write({'policy_generation':old+7});self.assertEqual(scopes.current_scope(self.native).policy_generation,old+7)
    def test_current_asymmetric_roles_and_foreign_native_records_stay_denied(self):
        viewer=self.actor('alice','B');self.assertEqual(scopes.current_scope(viewer).role,'viewer');self.denied(lambda:viewer['mp.example.note'].browse([])._mp_guard('write'))
        self.cr.execute('SELECT id FROM mp_example_note WHERE public_id=%s',[SEED['note_id']]);ident=self.cr.fetchone()[0]
        self.denied(lambda:viewer['mp.example.note'].browse(ident).read(['public_id']))
    def test_wrong_backing_user_cannot_reuse_typed_scope(self):
        wrong=api.Environment(self.cr,FIXTURE['users']['bob']['id'],self.native.context);self.denied(lambda:scopes.current_scope(wrong))
    def test_forged_dict_cannot_replace_native_scope(self):
        wrong=self.native(context={'_mp_scope':{'workspace_id':FIXTURE['workspaces']['C']['id']}});self.denied(lambda:scopes.current_scope(wrong))
    def technical(self):
        self.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['worker']['principal_id']]);principal=self.cr.fetchone()[0]
        member=ENV['mp.membership'].search([('principal_id','=',principal),('workspace_id','=',FIXTURE['workspaces']['A']['id'])]);member.write({'role':'editor'})
        installation=FIXTURE['bindings']['A']['consumer_installation_id']
        credential=ENV['mp.service.credential'].create(dict(name='Owned rollback policy credential',principal_id=principal,workspace_id=FIXTURE['workspaces']['A']['id'],token_digest=hashlib.sha256(uuid4().bytes).hexdigest(),installation_public_id=installation,actions='read,write',expires_at=fields.Datetime.now()+timedelta(minutes=5)))
        raw=api.Environment(self.cr,FIXTURE['users']['worker']['id'],{})
        initial=scopes.resolve_scope(raw,FIXTURE['workspaces']['A']['public_id']);initial=replace(initial,credential_id=credential.id,allowed_actions=frozenset({'read','write'}))
        native=raw(context={'_mp_scope':scopes.resolve_scope(raw,initial.workspace_public_id,previous=initial)})
        self.assertNotEqual(native.uid,1);self.assertEqual(scopes.current_scope(native).principal_kind,'service')
        native['mp.example.note'].browse([])._mp_guard('write');return credential,native
    def test_pending_credential_revocation_denies_current_scope(self):
        credential,native=self.technical();credential.write({'state':'revoked'});self.denied(lambda:scopes.current_scope(native))
    def test_pending_credential_expiry_denies_current_scope(self):
        credential,native=self.technical();credential.write({'expires_at':fields.Datetime.now()-timedelta(seconds=1)});self.denied(lambda:scopes.current_scope(native))
    def test_pending_credential_audience_change_denies_current_scope(self):
        credential,native=self.technical();credential.write({'audience':'owned-other-audience'});self.denied(lambda:scopes.current_scope(native))
    def test_pending_credential_workspace_change_cannot_move_actor_scope(self):
        credential,native=self.technical();credential.write({'workspace_id':FIXTURE['workspaces']['B']['id']});self.denied(lambda:scopes.current_scope(native))
    def test_pending_credential_action_narrowing_blocks_native_write(self):
        credential,native=self.technical();credential.write({'actions':'read'});self.assertEqual(scopes.current_scope(native).allowed_actions,frozenset({'read'}));self.denied(lambda:native['mp.example.note'].browse([])._mp_guard('write'))
    def test_service_mapping_without_credential_has_no_human_fallback(self):
        self.principal.write({'kind':'service'});self.denied(lambda:self.native['mp.example.note'].browse([])._mp_guard('read'));self.denied(self.retry)
