"""Opt-in primitive tests inside a real native registry and owned PostgreSQL.

The driver supplies ENV and FIXTURE only on the explicitly disposable G6 DB.
These are prerequisite integration checks, not complete G6 acceptance.
"""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from uuid import uuid4

from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from modular_platform import durable as queue


class DurablePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=ENV.registry
        cls.fixture=FIXTURE
        cls.site=FIXTURE['site_id']
        cls.workspace=FIXTURE['workspaces']['A']
        cls.actor=FIXTURE['users']['alice']
        cls.handlers=[]
        with cls.registry.cursor() as cr:
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");assert cr.fetchone()[0]==cls.site
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");cls.release=cr.fetchone()[0]
            cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[cls.actor['principal_id']]);cls.actor_id=cr.fetchone()[0]
            cr.execute("SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.notes' AND state='installed'");cls.installation=cr.fetchone()[0]
            assert cr.dbname.startswith('mp_disposable_r0_r1_g6_')
            queue.set_control(cr,cls.site,cls.release,'enabled');cr.commit()

    @classmethod
    def tearDownClass(cls):
        # Explicitly hold only this suite's still-pending synthetic work. Keep
        # all rows/effects/uncertainty for inspection; never drain real user work.
        with cls.registry.cursor() as cr:
            queue.set_control(cr,cls.site,cls.release,'paused')
            cr.execute("UPDATE mp_job SET state='held',lease_owner=NULL,lease_until=NULL WHERE handler=ANY(%s) AND state IN ('pending','retry','running')",[cls.handlers])
            cr.commit()

    def setUp(self):
        self.handler='org.example.notes:primitive.'+uuid4().hex
        self.handlers.append(self.handler)
        self.scope=queue.DispatchScope(self.site,self.workspace['id'],self.actor_id,self.installation,self.release)
        with self.registry.cursor() as cr:
            queue.set_control(cr,self.site,self.release,'enabled')
            native=self.native(cr)
            row=native['mp.example.note'].create(dict(title='G6 primitive proof '+uuid4().hex,body='Synthetic reference text'))
            self.note_id=row.id;self.public_id=row.public_id;self.original_title=row.title
            cr.commit()

    def native(self,cr):
        return scoped_environment(api.Environment(cr,self.actor['id'],{}),self.workspace['public_id'])

    def enqueue(self,**options):
        with self.registry.cursor() as cr:
            ident=queue.enqueue(cr,self.scope,self.handler,1,dict(note_id=self.public_id),'one',**options);cr.commit();return ident

    def claim(self,**options):
        with self.registry.cursor() as cr:
            value=queue.claim(cr,self.site,self.release,str(uuid4()),[self.handler],**options);cr.commit();return value

    def row(self,ident):
        with self.registry.cursor() as cr:
            cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident]);row=cr.fetchone();return row[0] if row else None

    def note(self):
        with self.registry.cursor() as cr:
            row=self.native(cr)['mp.example.note'].browse(self.note_id)
            return dict(title=row.title,revision=row.revision)

    def write(self,cr,title):
        native=self.native(cr);row=native['mp.example.note'].browse(self.note_id)
        row.with_context(expected_revision=row.revision).write(dict(title=title))
        native.flush_all()
        return dict(revision=row.revision)

    def expire(self):
        with self.registry.cursor() as cr:cr.execute('SELECT pg_sleep(1.1)')

    def test_atomic_claim_across_two_real_connections(self):
        ident=self.enqueue();barrier=threading.Barrier(2)
        def worker(_):
            from psycopg2.errors import SerializationFailure
            with self.registry.cursor() as cr:
                barrier.wait(timeout=10)
                try:value=queue.claim(cr,self.site,self.release,str(uuid4()),[self.handler]);cr.commit();return value
                except SerializationFailure:cr.rollback();return 'serialization_refusal'
        with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(worker,range(2)))
        self.assertEqual(sum(isinstance(c,queue.Claim) for c in claims),1)
        self.assertEqual(self.row(ident)['attempts'],1)

    def test_cancel_is_scoped_and_running_claim_cannot_mutate(self):
        ident=self.enqueue();value=self.claim(lease_seconds=1)
        with self.registry.cursor() as cr:
            self.assertFalse(queue.cancel(cr,ident,actor_id=self.actor_id,workspace_id=self.fixture['workspaces']['B']['id']))
            queue.heartbeat(cr,value,lease_seconds=1,progress=25)
            self.assertTrue(queue.cancel(cr,ident,actor_id=self.actor_id,workspace_id=self.workspace['id']));cr.commit()
        with self.registry.cursor() as cr:
            with self.assertRaises(queue.ClaimLost):queue.run_fenced(cr,value,lambda record:self.write(cr,'Must not write'))
            cr.commit()
        self.assertEqual(self.note()['revision'],1)
        self.expire();self.assertIsNone(self.claim());self.assertEqual(self.row(ident)['state'],'cancelled')

    def test_deadline_expires_without_starting_business_work(self):
        ident=self.enqueue(timeout_seconds=1);self.expire()
        self.assertIsNone(self.claim());self.assertEqual(self.row(ident)['state'],'dead_letter')
        self.assertEqual(self.row(ident)['error_code'],'DEADLINE_EXCEEDED');self.assertEqual(self.note()['revision'],1)

    def test_enqueue_rolls_back_and_dedup_input_conflicts(self):
        with self.registry.cursor() as cr:
            abandoned=queue.enqueue(cr,self.scope,self.handler,1,{},'rollback');cr.rollback()
        self.assertIsNone(self.row(abandoned))
        ident=self.enqueue()
        with self.registry.cursor() as cr:
            self.assertEqual(queue.enqueue(cr,self.scope,self.handler,1,dict(note_id=self.public_id),'one'),ident)
            with self.assertRaises(queue.QueueError):queue.enqueue(cr,self.scope,self.handler,1,dict(note_id=str(uuid4())),'one')
            cr.commit()
        self.assertEqual(self.row(ident)['attempts'],0)

    def test_late_expiry_rolls_back_actual_native_write(self):
        ident=self.enqueue();value=self.claim(lease_seconds=1)
        with self.registry.cursor() as cr:
            def work(record):
                result=self.write(cr,'Uncommitted native change');cr.execute('SELECT pg_sleep(1.1)');return result
            with self.assertRaises(queue.ClaimLost):queue.run_fenced(cr,value,work,flush=self.native(cr).flush_all)
            cr.commit()
        self.assertEqual(self.note(),dict(title=self.original_title,revision=1))
        self.assertEqual(self.row(ident)['state'],'running')

    def test_lease_reclaim_fences_obsolete_native_mutation_and_completed_replay(self):
        ident=self.enqueue();old=self.claim(lease_seconds=1);self.expire();new=self.claim()
        self.assertEqual(new.generation,old.generation+1)
        with self.registry.cursor() as cr:
            with self.assertRaises(queue.ClaimLost):queue.run_fenced(cr,old,lambda record:self.write(cr,'Obsolete must not commit'))
            cr.commit()
        with self.registry.cursor() as cr:
            result=queue.run_fenced(cr,new,lambda record:self.write(cr,'Current claim committed'),flush=self.native(cr).flush_all);cr.commit()
        self.assertEqual(result,dict(revision=2));self.assertEqual(self.note(),dict(title='Current claim committed',revision=2))
        with self.registry.cursor() as cr:
            with self.assertRaises(queue.ClaimLost):queue.run_fenced(cr,new,lambda record:self.write(cr,'Duplicate must not commit'))
            cr.commit()
        self.assertEqual(self.note()['revision'],2);self.assertEqual(self.row(ident)['attempts'],2);self.assertEqual(self.row(ident)['state'],'completed')

    def test_native_control_metadata_has_no_human_CRUD_authority(self):
        for model in ['mp.job','mp.outbox','mp.dispatch.control']:
            with self.registry.cursor() as cr:
                native=self.native(cr)
                with self.assertRaises(AccessError):native[model].search_count([])

    def test_nonidempotent_lost_claim_reports_uncertainty_without_retry(self):
        ident=self.enqueue(effect_mode='reconcile');value=self.claim(lease_seconds=1)
        with self.registry.cursor() as cr:queue.effect_started(cr,value);cr.commit()
        self.expire();self.assertIsNone(self.claim())
        self.assertEqual(self.row(ident)['state'],'outcome_unknown');self.assertEqual(self.row(ident)['attempts'],1)
        self.assertEqual(self.note()['revision'],1)

    def test_outbox_shares_native_business_commit_and_rollback(self):
        def event(cr):
            return queue.append_event(cr,self.scope,plugin_id='org.example.notes',topic='org.example.notes.changed',version=1,aggregate_id=self.public_id,payload=dict(note_id=self.public_id,revision=2),correlation_id=str(uuid4()),sequence=2)
        with self.registry.cursor() as cr:
            self.write(cr,'Rolled back producer');abandoned=event(cr);cr.rollback()
        with self.registry.cursor() as cr:
            cr.execute('SELECT count(*) FROM mp_outbox WHERE public_id=%s',[abandoned]);self.assertEqual(cr.fetchone()[0],0)
        self.assertEqual(self.note()['revision'],1)
        with self.registry.cursor() as producer:
            self.write(producer,'Committed producer');ident=event(producer)
            with self.registry.cursor() as observer:
                observer.execute('SELECT count(*) FROM mp_outbox WHERE public_id=%s',[ident]);self.assertEqual(observer.fetchone()[0],0)
            producer.commit()
        with self.registry.cursor() as observer:
            observer.execute('SELECT payload,workspace_id,actor_id FROM mp_outbox WHERE public_id=%s',[ident]);row=observer.fetchone()
            self.assertEqual(row,(dict(note_id=self.public_id,revision=2),self.workspace['id'],self.actor_id))
        self.assertEqual(self.note()['revision'],2)

    def test_pause_and_release_generation_invalidate_old_claim(self):
        ident=self.enqueue();value=self.claim()
        with self.registry.cursor() as cr:old=queue.set_control(cr,self.site,self.release,'paused');cr.commit()
        with self.registry.cursor() as cr:
            with self.assertRaises(queue.DispatchPaused):queue.enqueue(cr,self.scope,self.handler,1,{},'paused')
            with self.assertRaises(queue.DispatchPaused):queue.run_fenced(cr,value,lambda record:self.write(cr,'Paused must not commit'))
        with self.registry.cursor() as cr:new=queue.set_control(cr,self.site,self.release,'enabled');cr.commit()
        self.assertGreater(new,old)
        with self.registry.cursor() as cr:
            with self.assertRaises(queue.ClaimLost):queue.run_fenced(cr,value,lambda record:self.write(cr,'Old generation must not commit'))
            cr.commit()
        self.assertEqual(self.note()['revision'],1)

    def test_retry_backoff_and_dead_letter_are_bounded(self):
        ident=self.enqueue(max_attempts=2);value=self.claim()
        with self.registry.cursor() as cr:
            self.assertEqual(queue.fail(cr,value,'DEPENDENCY_UNAVAILABLE',retryable=True),'retry');cr.commit()
        self.assertIsNone(self.claim());self.expire();value=self.claim();self.assertIsNotNone(value)
        with self.registry.cursor() as cr:
            self.assertEqual(queue.fail(cr,value,'INTERNAL_ERROR',retryable=False),'dead_letter');cr.commit()
        self.assertIsNone(self.claim());self.assertEqual(self.row(ident)['attempts'],2)
