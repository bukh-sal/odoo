"""Actual native/PostgreSQL lifecycle fences; all fixture writes roll back."""
import copy,json,threading,time,unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events,job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import durable


class DispatchLifecycleTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();self.cr=ENV.cr;self.cr.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");self.site=self.cr.fetchone()[0];assert self.site==FIXTURE['site_id']
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.release=self.cr.fetchone()[0]
        self.scope=LC.LifecycleScope(self.site,self.release);self.baseline=LC.observe(self.cr,self.scope)
        durable.set_control(self.cr,self.site,self.release,'enabled')
        self.native=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
    def tearDown(self):
        ENV.cr.rollback();self.assertEqual(LC.observe(ENV.cr,self.scope),self.baseline);ENV.cr.rollback()
    def call(self,kind,**values):
        return events.dispatch(self.native,dict(protocol=1,kind=kind+'_request',request_id=str(uuid4()),**values),binding_id=FIXTURE['bindings']['A']['binding_id'])
    def subscription(self):
        ident=self.call('subscribe',topic='org.example.notes.changed',idempotency_key=str(uuid4()))['subscription_id']
        self.note=self.native['mp.example.note'].create(dict(title='Lifecycle  rollback  owned'));self.native.flush_all()
        batch=self.call('poll',subscription_id=ident,limit=50)['deliveries'];target=next(d for d in batch if d['event']['aggregate_id']==self.note.public_id)
        return ident,dict(delivery_id=target['id'],receipt=target['receipt'],generation=target['generation'])
    def job(self,effect='idempotent'):
        self.cr.execute("SELECT id,public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes'");installation,consumer=self.cr.fetchone()
        if effect=='idempotent':
            self.note=self.native['mp.example.note'].create(dict(title='Lifecycle  job  owned'))
            frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['A']['public_id'],self.site,consumer,'org.example.notes',())
            native=self.native(context={**self.native.context,'_mp_call_frame':frame})
            ident=jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=self.note.public_id,expected_revision=1),uuid4().hex)
            invocation=jobs.prepare_one(ENV,str(uuid4()));self.assertEqual(invocation.claim.job_id,ident);return ident,invocation
        self.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']]);actor=self.cr.fetchone()[0]
        scope=durable.DispatchScope(self.site,FIXTURE['workspaces']['A']['id'],actor,installation,self.release)
        ident=durable.enqueue(self.cr,scope,'org.example.notes:rollback_uncertain',1,{},uuid4().hex,effect_mode='reconcile')
        claim=durable.claim(self.cr,self.site,self.release,str(uuid4()),['org.example.notes:rollback_uncertain']);durable.effect_started(self.cr,claim)
        return ident,claim
    def test_fence_preserves_history_and_is_transactional(self):
        sub,receipt=self.subscription();ident,invocation=self.job();unknown,_=self.job('reconcile')
        before=LC.observe(self.cr,self.scope);proof=LC.fence(self.cr,self.scope,str(uuid4()));after=proof['after']
        self.assertEqual(after['control']['state'],'paused');self.assertEqual(after['control']['generation'],before['control']['generation']+1)
        for table in ['mp_outbox','mp_event_consumption','mp_event_consumer_state']:self.assertEqual(before['tables'][table],after['tables'][table])
        self.cr.execute('SELECT public_id,state,lease_owner FROM mp_job WHERE public_id=ANY(%s)',[[ident,unknown]])
        self.assertEqual({r[0]:(r[1],r[2]) for r in self.cr.fetchall()},{ident:('held',None),unknown:('outcome_unknown',None)})
        self.cr.execute('SELECT state FROM mp_event_subscription WHERE public_id=%s',[sub]);self.assertEqual(self.cr.fetchone()[0],'closed')
        self.cr.execute('SELECT receipt,generation FROM mp_event_delivery WHERE public_id=%s',[receipt['delivery_id']]);token,generation=self.cr.fetchone();self.assertIsNone(token);self.assertGreater(generation,receipt['generation'])
    def test_old_job_cannot_apply_native_effect_after_pause_resume(self):
        ident,invocation=self.job();computed=jobs.compute(invocation);self.native.flush_all();old_title=self.note.title
        LC.fence(self.cr,self.scope,str(uuid4()));durable.set_control(self.cr,self.site,self.release,'enabled')
        with self.assertRaises(durable.ClaimLost):jobs.finish_one(ENV,invocation,computed)
        self.assertEqual((self.note.title,self.note.revision),(old_title,1))
    def test_old_event_receipt_cannot_acknowledge_after_pause_resume(self):
        sub,receipt=self.subscription();LC.fence(self.cr,self.scope,str(uuid4()));durable.set_control(self.cr,self.site,self.release,'enabled')
        with self.assertRaises(PublicError) as error:self.call('ack',subscription_id=sub,receipts=[receipt])
        self.assertEqual(error.exception.code,'CONFLICT')
        self.cr.execute('SELECT count(*) FROM mp_event_delivery WHERE public_id=%s AND state=\'acknowledged\'',[receipt['delivery_id']]);self.assertEqual(self.cr.fetchone()[0],0)
    def test_partial_schema_and_missing_dedup_constraint_are_refused(self):
        self.cr.execute('ALTER TABLE mp_event_delivery RENAME COLUMN receipt TO unexpected_receipt')
        with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,self.scope,str(uuid4()))
        self.cr.execute('ALTER TABLE mp_event_delivery RENAME COLUMN unexpected_receipt TO receipt')
        self.cr.execute("SELECT k.conname FROM pg_constraint k WHERE k.conrelid='mp_event_consumption'::regclass AND k.contype='u' AND array_length(k.conkey,1)=4")
        name=self.cr.fetchone()[0];self.cr.execute('ALTER TABLE mp_event_consumption DROP CONSTRAINT '+ '"'+name.replace('"','""')+'"')
        with self.assertRaises(LC.DispatchLifecycleError):LC.observe(self.cr,self.scope)
    def test_foreign_site_and_changed_release_are_refused(self):
        for scope in [LC.LifecycleScope(str(uuid4()),self.release),LC.LifecycleScope(self.site,'sha256:'+'0'*64),dict(site_id=self.site,release_digest=self.release)]:
            with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,scope,str(uuid4()))
        self.assertEqual(LC.observe(self.cr,self.scope)['control']['state'],'enabled')
    def test_unknown_state_or_external_runtime_prevents_fencing(self):
        ident,_=self.job();self.cr.execute("UPDATE mp_job SET state='unexpected' WHERE public_id=%s",[ident])
        with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,self.scope,str(uuid4()))
        self.cr.execute("UPDATE mp_job SET state='running' WHERE public_id=%s",[ident])
        self.cr.execute("UPDATE mp_plugin_installation SET runtime='service' WHERE plugin_id='org.example.notes'")
        with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,self.scope,str(uuid4()))
        self.assertEqual(LC.observe(self.cr,self.scope)['control']['state'],'enabled')
    def test_generation_exhaustion_refuses_before_any_update(self):
        self.cr.execute('UPDATE mp_dispatch_control SET generation=%s',[2**31-1]);before=LC.observe(self.cr,self.scope)
        with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,self.scope,str(uuid4()))
        self.assertEqual(LC.observe(self.cr,self.scope),before)
    def _native_drain(self,commit=False):
        # This case commits the operator fence (control epoch and obsolete
        # receipt metadata); the producer's Note/outbox roll back.
        self.cr.rollback();original=LC.observe(self.cr,self.scope)
        with ENV.registry.cursor() as cr:durable.set_control(cr,self.site,self.release,'enabled');cr.commit()
        producer=ENV.registry.cursor();started=threading.Event();pid=[]
        try:
            native=scoped_environment(api.Environment(producer,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
            note=native['mp.example.note'].create(dict(title='Actual native drain blocker'));native.flush_all();ident=note.public_id
            producer.execute('SELECT pg_backend_pid()');producer_pid=producer.fetchone()[0]
            def drain():
                with ENV.registry.cursor() as cr:
                    cr.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
                    cr.execute('SET LOCAL lock_timeout=\'8s\'');cr.execute('SELECT pg_backend_pid()');pid.append(cr.fetchone()[0]);started.set()
                    result=LC.fence(cr,self.scope,str(uuid4()));cr.commit();return result
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(drain);self.assertTrue(started.wait(3))
                deadline=time.monotonic()+3;blocked=False
                while time.monotonic()<deadline:
                    with ENV.registry.cursor() as cr:
                        cr.execute('SELECT pg_blocking_pids(%s)',[pid[0]]);blocked=producer_pid in cr.fetchone()[0]
                    if blocked:break
                    time.sleep(.02)
                self.assertTrue(blocked,'Drain did not wait on the real native transaction');self.assertFalse(future.done())
                producer.commit() if commit else producer.rollback()
                result=future.result(timeout=10);self.assertEqual(result['after']['control']['state'],'paused')
            with ENV.registry.cursor() as cr:
                cr.execute('SELECT count(*) FROM mp_example_note WHERE public_id=%s',[ident]);self.assertEqual(cr.fetchone()[0],int(commit))
                cr.execute('SELECT count(*) FROM mp_outbox WHERE aggregate_id=%s',[ident]);self.assertEqual(cr.fetchone()[0],int(commit))
        finally:producer.rollback();producer.close()
        self.cr.rollback();after=LC.observe(self.cr,self.scope)
        self.assertEqual(after['control']['generation'],original['control']['generation']+2)
        for table in set(original['tables'])-{'mp_dispatch_control','mp_event_delivery'}-({'mp_outbox'} if commit else set()):self.assertEqual(after['tables'][table],original['tables'][table])
        if commit:self.assertEqual(after['tables']['mp_outbox']['rows'],original['tables']['mp_outbox']['rows']+1)
        self.assertEqual(result['before']['tables']['mp_outbox'],result['after']['tables']['mp_outbox'])
        self.assertEqual(after,result['after'])
        self.baseline=after
    def test_real_native_producer_holds_drain_until_its_transaction_finishes(self):self._native_drain()
    def test_real_native_commit_is_included_after_drain_wait(self):self._native_drain(commit=True)
    def test_repeatable_read_drain_is_rejected_before_mutation(self):
        self.cr.rollback();self.cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');before=LC.observe(self.cr,self.scope)
        with self.assertRaises(LC.DispatchLifecycleError):LC.fence(self.cr,self.scope,str(uuid4()))
        self.assertEqual(LC.observe(self.cr,self.scope),before)
