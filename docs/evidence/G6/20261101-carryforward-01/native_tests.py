"""Real native original-user carry-forward; all test writes roll back."""
import copy,json,unittest
from dataclasses import replace
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError


class CarryForwardTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();self.cr=ENV.cr;self.cr.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.old=self.cr.fetchone()[0]
        self.site=FIXTURE['site_id'];self.scope=LC.LifecycleScope(self.site,self.old);self.baseline=LC.observe(self.cr,self.scope)
        self.cr.execute('SELECT count(*) FROM mp_example_note');self.note_count=self.cr.fetchone()[0]
        self.cr.execute('SELECT public_id,descriptor FROM mp_service_binding WHERE public_id=%s',[FIXTURE['bindings']['A']['binding_id']]);self.binding_id,self.binding=self.cr.fetchone()
        self.new='sha256:'+'d'*64;assert self.new!=self.old
        jobs.DEFINITIONS=DEFINITIONS.copy();store.set_control(self.cr,self.site,self.old,'enabled')
        self.native=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
        frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['A']['public_id'],self.site,self.binding['consumer_installation_id'],'org.example.notes',())
        self.native=self.native(context={**self.native.context,'_mp_call_frame':frame})
    def tearDown(self):
        ENV.cr.rollback();self.assertEqual(LC.observe(self.cr,self.scope),self.baseline)
        self.cr.execute('SELECT count(*) FROM mp_example_note');self.assertEqual(self.cr.fetchone()[0],self.note_count);ENV.cr.rollback()
    def enqueue(self,handler='normalize_title'):
        self.note=self.native['mp.example.note'].create(dict(title='Carry   forward  original actor'))
        self.values=dict(note_id=self.note.public_id,expected_revision=1);self.key=uuid4().hex;self.trace=str(uuid4())
        self.ident=jobs.enqueue_bound(self.native,'documents','org.example.notes:'+handler,self.values,self.key,request_id=self.trace)
        return self.ident
    def row(self,ident=None):
        self.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident or self.ident]);return self.cr.fetchone()[0]
    def publish(self,change=None):
        LC.fence(self.cr,self.scope,str(uuid4()))
        self.cr.execute("UPDATE ir_config_parameter SET value=%s WHERE key='mp.release_digest'",[self.new])
        binding=copy.deepcopy(self.binding);binding['generation']+=1
        if change:binding.update(change)
        self.cr.execute('UPDATE mp_service_binding SET descriptor=%s::jsonb WHERE public_id=%s',[json.dumps(binding),self.binding_id])
        return binding
    def reconcile(self):return jobs.reconcile_release(ENV,previous_release=self.old,target_release=self.new)
    def decision(self,result,ident=None):return next(d for d in result['jobs'] if d['job_id']==(ident or self.ident))
    def test_compatible_pending_job_preserves_semantics_trace_and_original_user(self):
        self.enqueue();old=self.row();binding=self.publish();result=self.reconcile();after=self.row()
        self.assertTrue(result['resume_allowed']);self.assertFalse(result['dispatch_enabled']);self.assertEqual(self.decision(result)['decision'],'resumable')
        self.assertEqual(after['payload']['context']['binding'],binding);self.assertEqual(after['release_digest'],self.new)
        for key in ['actor_id','workspace_id','installation_id','idempotency_key','attempts','deadline_at']:self.assertEqual(old[key],after[key])
        self.assertEqual(after['payload']['context']['request_id'],self.trace);self.assertEqual(after['payload']['input'],old['payload']['input'])
        store.set_control(self.cr,self.site,self.new,'enabled');invocation=jobs.prepare_one(ENV,str(uuid4()));self.assertEqual(invocation.claim.job_id,self.ident)
        self.assertEqual(jobs.finish_one(ENV,invocation,jobs.compute(invocation))['revision'],2)
        self.note.invalidate_recordset();self.assertEqual(self.note.write_uid.id,FIXTURE['users']['alice']['id'])
        self.assertEqual(jobs.enqueue_bound(self.native,'documents','org.example.notes:normalize_title',self.values,self.key,request_id=str(uuid4())),self.ident)
        self.assertEqual(self.row()['payload']['context']['request_id'],self.trace)
    def test_old_claim_cannot_apply_after_compatible_rebind(self):
        self.enqueue();old=jobs.prepare_one(ENV,str(uuid4()));computed=jobs.compute(old);self.publish();self.reconcile();store.set_control(self.cr,self.site,self.new,'enabled')
        with self.assertRaises(store.ClaimLost):jobs.finish_one(ENV,old,computed)
        new=jobs.prepare_one(ENV,str(uuid4()));self.assertEqual(self.row()['attempts'],2)
        jobs.finish_one(ENV,new,jobs.compute(new));self.note.invalidate_recordset();self.assertEqual(self.note.revision,2)
        self.cr.execute('SELECT count(*) FROM mp_outbox WHERE aggregate_id=%s AND aggregate_sequence=2',[self.note.public_id]);self.assertEqual(self.cr.fetchone()[0],1)
    def test_completed_outcome_is_carried_without_reapplying(self):
        self.enqueue();invocation=jobs.prepare_one(ENV,str(uuid4()));outcome=jobs.finish_one(ENV,invocation,jobs.compute(invocation));before=self.row()
        self.publish();result=self.reconcile();after=self.row();self.assertEqual(self.decision(result)['decision'],'retained_terminal')
        self.assertEqual((after['state'],after['result'],after['attempts']),('completed',outcome,before['attempts']))
        self.assertEqual(jobs.status(self.native,self.ident)['result'],outcome);self.note.invalidate_recordset();self.assertEqual(self.note.revision,2)
    def test_api_major_change_is_held_not_adopted(self):
        self.enqueue();old=self.row();self.publish(dict(contract_major=2,api_version='2.0'));result=self.reconcile();after=self.row()
        self.assertEqual(after['state'],'held');self.assertEqual(after['release_digest'],self.old);self.assertEqual(after['payload'],old['payload']);self.assertEqual(self.decision(result)['error_code'],'VALIDATION_FAILED')
    def test_valid_new_major_still_cannot_adopt_old_job(self):
        self.enqueue('inspect_revision');self.publish(dict(contract_major=2,api_version='2.0'))
        self.cr.execute("SELECT manifest FROM mp_plugin_installation WHERE plugin_id='org.example.notes'");manifest=self.cr.fetchone()[0]
        requirement=next(r for r in manifest['services']['requires'] if r['alias']=='documents');requirement.update(contract_major=2,version='>=2.0,<3.0')
        self.cr.execute("UPDATE mp_plugin_installation SET manifest=%s::jsonb WHERE plugin_id='org.example.notes'",[json.dumps(manifest)])
        key=('org.example.notes:inspect_revision',1);jobs.DEFINITIONS[key]=replace(jobs.DEFINITIONS[key],api_version='2.0')
        result=self.reconcile();self.assertEqual(self.decision(result)['error_code'],'CONFLICT');self.assertEqual(self.row()['state'],'held');self.assertEqual(self.row()['payload']['context']['binding']['contract_major'],1)
    def test_revoked_role_and_removed_handler_never_get_administrator_fallback(self):
        self.enqueue();self.publish();self.cr.execute("UPDATE mp_membership SET role='viewer' WHERE workspace_id=%s AND principal_id=(SELECT id FROM mp_principal WHERE public_id=%s)",[FIXTURE['workspaces']['A']['id'],FIXTURE['users']['alice']['principal_id']])
        result=self.reconcile();self.assertEqual(self.decision(result)['error_code'],'FORBIDDEN');self.assertEqual(self.row()['state'],'held');self.assertEqual(self.note.revision,1)
    def test_missing_handler_is_held(self):
        self.enqueue();self.publish();jobs.DEFINITIONS.pop(('org.example.notes:normalize_title',1));result=self.reconcile()
        self.assertEqual(self.decision(result)['error_code'],'DEPENDENCY_UNAVAILABLE');self.assertEqual(self.row()['state'],'held')
    def test_changed_resource_revision_is_held_without_overwrite(self):
        self.enqueue();self.note.with_context(expected_revision=1).write(dict(title='Current user edit'));self.publish();result=self.reconcile()
        self.assertEqual(self.decision(result)['error_code'],'CONFLICT');self.note.invalidate_recordset();self.assertEqual((self.note.title,self.note.revision),('Current user edit',2))
    def test_deadline_and_attempt_limits_are_not_reset_by_release(self):
        self.enqueue();self.publish();self.cr.execute("UPDATE mp_job SET deadline_at=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[self.ident]);self.reconcile()
        self.assertEqual((self.row()['state'],self.row()['error_code']),('dead_letter','DEADLINE_EXCEEDED'))
    def test_tampered_semantic_digest_is_not_reinterpreted(self):
        self.enqueue();self.publish();self.cr.execute('UPDATE mp_job SET input_digest=%s WHERE public_id=%s',['sha256:'+'0'*64,self.ident]);result=self.reconcile()
        self.assertEqual(self.decision(result)['error_code'],'VALIDATION_FAILED');self.assertEqual(self.row()['state'],'held')
    def test_attempt_budget_is_not_refilled(self):
        self.enqueue();self.publish();self.cr.execute('UPDATE mp_job SET attempts=max_attempts WHERE public_id=%s',[self.ident]);self.reconcile();after=self.row()
        self.assertEqual((after['state'],after['error_code']),('dead_letter','LEASE_EXPIRED'));self.assertEqual(after['attempts'],after['max_attempts'])
    def test_unknown_external_outcome_prevents_dispatch_resume(self):
        self.enqueue();self.publish()
        # Explicit trusted fixture metadata only; no external effect is executed.
        self.cr.execute("UPDATE mp_job SET effect_mode='reconcile',effect_started=true,state='outcome_unknown' WHERE public_id=%s",[self.ident]);before=self.row();result=self.reconcile()
        self.assertFalse(result['resume_allowed']);self.assertEqual(self.decision(result)['decision'],'requires_effect_reconciliation');self.assertEqual(self.row(),before)
        self.cr.execute('SELECT state FROM mp_dispatch_control');self.assertEqual(self.cr.fetchone()[0],'paused')
    def test_unfenced_work_and_wrong_release_are_refused_before_rewrite(self):
        self.enqueue();before=self.row()
        with self.assertRaises(PublicError):jobs.reconcile_release(ENV,previous_release=self.old,target_release='sha256:'+'0'*64)
        self.assertEqual(self.row(),before)
        self.cr.execute("UPDATE ir_config_parameter SET value=%s WHERE key='mp.release_digest'",[self.new])
        with self.assertRaises(PublicError):self.reconcile()
        self.assertEqual(self.row(),before)
    def test_restored_fence_requires_exact_prior_control_release(self):
        self.enqueue();self.publish();source=LC.LifecycleScope(self.site,self.new,self.old);before=LC.observe(self.cr,source)
        with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,LC.LifecycleScope(self.site,self.new,'sha256:'+'0'*64),str(uuid4()))
        self.assertEqual(LC.observe(self.cr,source),before)
        proof=LC.fence(self.cr,source,str(uuid4()));self.assertEqual(proof['before']['control']['release_digest'],self.old)
        self.assertEqual(proof['after']['control']['release_digest'],self.new);self.assertEqual(proof['after']['control']['state'],'paused')
        self.assertEqual(proof['before']['tables']['mp_outbox'],proof['after']['tables']['mp_outbox'])
    def test_enable_rejects_stale_snapshot_then_uses_current_reconciled_state(self):
        self.enqueue();self.publish();self.reconcile();scope=LC.LifecycleScope(self.site,self.new);before=LC.observe(self.cr,scope)
        with self.assertRaises(LC.DispatchLifecycleError):LC.enable(self.cr,scope,'sha256:'+'0'*64)
        self.cr.execute('UPDATE mp_job SET progress=1 WHERE public_id=%s',[self.ident])
        with self.assertRaises(LC.DispatchLifecycleError):LC.enable(self.cr,scope,before['state_digest'])
        current=LC.observe(self.cr,scope);result=LC.enable(self.cr,scope,current['state_digest'])
        self.assertTrue(result['dispatch_enabled']);self.assertEqual(result['after']['control']['state'],'enabled')
    def test_enable_cannot_bypass_unknown_effect_reconciliation(self):
        self.enqueue();self.publish();self.cr.execute("UPDATE mp_job SET state='outcome_unknown',effect_mode='reconcile',effect_started=true WHERE public_id=%s",[self.ident]);result=self.reconcile();self.assertFalse(result['resume_allowed'])
        scope=LC.LifecycleScope(self.site,self.new);before=LC.observe(self.cr,scope)
        with self.assertRaises(LC.DispatchLifecycleError):LC.enable(self.cr,scope,before['state_digest'])
        self.assertEqual(LC.observe(self.cr,scope),before)
