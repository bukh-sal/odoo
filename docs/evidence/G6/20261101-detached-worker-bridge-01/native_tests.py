"""Native job provenance/regressions; every mutation rolls back."""
import unittest
from dataclasses import replace
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import dispatch_lifecycle as LC
from modular_platform.worker_dispatch import WorkerDispatchError

class JobProvenanceTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.release=self.cr.fetchone()[0]
        self.lifecycle=LC.LifecycleScope(FIXTURE['site_id'],self.release);self.before=LC.observe(self.cr,self.lifecycle)
        self.cr.execute('SELECT to_jsonb(n) FROM mp_example_note n ORDER BY id');self.notes=self.cr.fetchall()
        native=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id']);b=FIXTURE['bindings']['C']
        frame=CallFrame(FIXTURE['users']['alice']['principal_id'],b['workspace_id'],b['site_id'],b['consumer_installation_id'],'org.example.notes',())
        self.native=native(context={**native.context,'_mp_call_frame':frame})
        self.note=self.native['mp.example.note'].create(dict(title='Native  detached  provenance'))
        self.job=jobs.enqueue_bound(self.native,'documents','org.example.notes:normalize_title',dict(note_id=self.note.public_id,expected_revision=1),uuid4().hex)
        self.invocation=jobs.prepare_one(ENV,str(uuid4()))
    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(LC.observe(self.cr,self.lifecycle),self.before)
        self.cr.execute('SELECT to_jsonb(n) FROM mp_example_note n ORDER BY id');self.assertEqual(self.cr.fetchall(),self.notes);self.cr.rollback()
    def test_claim_provenance_and_original_actor_finish_are_preserved(self):
        self.assertEqual(self.invocation.database,self.cr.dbname);self.assertEqual(self.invocation.claim.job_id,self.job)
        computed=jobs.compute(self.invocation);result=jobs.finish_one(ENV,self.invocation,computed)
        self.assertEqual(result,dict(note_id=self.note.public_id,revision=2,changed=True))
        self.cr.execute('SELECT revision,write_uid,title FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone(),(2,FIXTURE['users']['alice']['id'],'Native detached provenance'))
    def test_context_provenance_is_overwritten_from_actual_invocation(self):
        key=self.invocation.handler,self.invocation.version;old=jobs.DEFINITIONS[key];captured=[]
        def compute(prepared,context):captured.append(context);return old.compute(prepared,context)
        jobs.DEFINITIONS[key]=replace(old,compute=compute)
        try:
            self.invocation.context['_native_job']={'database':'forged-selector'};jobs.compute(self.invocation)
        finally:jobs.DEFINITIONS[key]=old
        provenance=captured[0]['_native_job'];self.assertEqual(provenance['database'],self.cr.dbname)
        self.assertEqual(provenance['claim'],dict(job_id=self.job,generation=self.invocation.claim.generation,owner=self.invocation.claim.owner));self.assertEqual(provenance['fingerprint'],self.invocation.fingerprint)
    def test_worker_errors_have_safe_specific_codes_without_dynamic_text(self):
        for code in ['FORBIDDEN','DEPENDENCY_UNAVAILABLE','CONFLICT','DEADLINE_EXCEEDED','CANCELLED','VALIDATION_FAILED']:
            self.assertEqual(jobs._safe_code(WorkerDispatchError(code,sent=True)),code)
        self.assertEqual(jobs._safe_code(WorkerDispatchError('UNTRUSTED_DYNAMIC_MESSAGE')),'INTERNAL_ERROR')
        self.assertEqual(jobs._safe_code(AccessError('Private text')),'FORBIDDEN')
    def test_pending_actor_demotion_after_compute_blocks_business_effect(self):
        computed=jobs.compute(self.invocation);scope=self.native.context['_mp_scope'];member=ENV['mp.membership'].search([('principal_id','=',scope.principal_id),('workspace_id','=',scope.workspace_id)]);member.write({'role':'viewer'})
        result=jobs.finish_one(ENV,self.invocation,computed);self.assertEqual(result['error_code'],'FORBIDDEN')
        self.cr.execute('SELECT revision,title FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone(),(1,'Native  detached  provenance'))
