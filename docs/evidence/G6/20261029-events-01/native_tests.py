"""Real committed producers, inverse commits, consumers and current authority."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import hashlib,json,threading,unittest
from uuid import uuid4
from odoo import api,fields
from odoo.exceptions import AccessError
from odoo.service.model import retrying
from odoo.addons.mp_identity.scopes import scoped_environment,resolve_scope
from odoo.addons.mp_core import events
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import durable

HANDLER='org.example.notes_labels:revision_projection'


class NativeEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=ENV.registry;cls.fixture=FIXTURE;cls.owned=[]
        with cls.registry.cursor() as cr:
            assert cr.dbname.startswith('mp_disposable_r0_r1_g6_')
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");cls.site=cr.fetchone()[0];assert cls.site==FIXTURE['site_id']
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");cls.release=cr.fetchone()[0]
            durable.set_control(cr,cls.site,cls.release,'enabled');cr.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.registry.cursor() as cr:
            durable.set_control(cr,cls.site,cls.release,'paused');cr.commit()

    def env(self,cr,actor='alice',workspace='A',credential=None):
        native=scoped_environment(api.Environment(cr,FIXTURE['users'][actor]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
        if credential:
            scope=replace(resolve_scope(native,FIXTURE['workspaces'][workspace]['public_id']),credential_id=credential,allowed_actions=frozenset({'read','create','write'}))
            native=native(context={'_mp_scope':resolve_scope(native,scope.workspace_public_id,previous=scope)})
        return native

    def setUp(self):
        self.subs=[]
        with self.registry.cursor() as cr:durable.set_control(cr,self.site,self.release,'enabled');cr.commit()
        self.sub=self.subscribe()

    def tearDown(self):
        # Close only this suite's explicitly created streams, retaining every
        # event, receipt, failed outcome and business record for inspection.
        with self.registry.cursor() as cr:
            cr.execute("UPDATE mp_event_subscription SET state='closed' WHERE public_id=ANY(%s)",[self.subs]);cr.commit()

    def binding(self,cr,plugin='org.example.notes',workspace='A'):
        cr.execute("SELECT b.public_id FROM mp_service_binding b JOIN mp_plugin_installation i ON i.id=b.consumer_id WHERE i.plugin_id=%s AND b.workspace_id=%s AND b.alias='documents' AND b.state='active'",[plugin,FIXTURE['workspaces'][workspace]['id']]);return cr.fetchone()[0]

    def request(self,operation,*,actor='alice',workspace='A',credential=None,**values):
        with self.registry.cursor() as cr:
            result=events.dispatch(self.env(cr,actor,workspace,credential),dict(protocol=1,kind=operation+'_request',request_id=str(uuid4()),**values));cr.commit();return result

    def subscribe(self,plugin='org.example.notes',actor='alice',workspace='A',credential=None,*,drain=True):
        with self.registry.cursor() as cr:
            result=events.dispatch(self.env(cr,actor,workspace,credential),dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=self.binding(cr,plugin,workspace));cr.commit()
        ident=result['subscription_id'];self.subs.append(ident);self.owned.append(ident)
        if drain:
            for _ in range(50):
                items=self.request('poll',subscription_id=ident,limit=50,actor=actor,workspace=workspace,credential=credential)['deliveries']
                if not items:break
                self.ack(ident,items,actor=actor,workspace=workspace,credential=credential)
            else:raise AssertionError('Unexpected retained fixture history size')
        return ident

    def ack(self,ident,items,**scope):
        return self.request('ack',subscription_id=ident,receipts=[dict(delivery_id=item['id'],receipt=item['receipt'],generation=item['generation']) for item in items],**scope)

    def note(self,*,actor='alice',workspace='A'):
        with self.registry.cursor() as cr:
            native=self.env(cr,actor,workspace);note=native['mp.example.note'].create(dict(title='Committed event '+uuid4().hex,body='Synthetic minimized event proof'));public=note.public_id;cr.commit();return public

    def event(self,note):
        with self.registry.cursor() as cr:
            cr.execute('SELECT to_jsonb(o) FROM mp_outbox o WHERE aggregate_id=%s ORDER BY id',[note]);return [r[0] for r in cr.fetchall()]

    def consume(self,ident):
        with self.registry.cursor() as cr:
            native=self.env(cr)
            return retrying(lambda:events.consume_registered(native,ident,HANDLER),native)

    @contextmanager
    def changed(self,query,new,old):
        with self.registry.cursor() as cr:cr.execute(query,new);cr.commit()
        try:yield
        finally:
            with self.registry.cursor() as cr:cr.execute(query,old);cr.commit()

    def test_rollback_and_native_bus_are_commit_safe(self):
        with self.registry.cursor() as cr:
            cr.execute("SELECT count(*) FROM bus_bus WHERE message::jsonb->>'type'='mp_domain_events'");before=cr.fetchone()[0]
        with self.registry.cursor() as producer:
            native=self.env(producer);note=native['mp.example.note'].create(dict(title='Rolled-back event'));public=note.public_id;native.flush_all()
            self.assertEqual(self.request('poll',subscription_id=self.sub,limit=50)['deliveries'],[])
            producer.rollback()
        self.assertEqual(self.event(public),[])
        with self.registry.cursor() as cr:
            cr.execute("SELECT count(*) FROM bus_bus WHERE message::jsonb->>'type'='mp_domain_events'");self.assertEqual(cr.fetchone()[0],before)
        committed=self.note();items=self.request('poll',subscription_id=self.sub,limit=50)['deliveries'];self.assertEqual(len(items),1)
        self.assertEqual(items[0]['event']['aggregate_id'],committed)
        with self.registry.cursor() as cr:
            cr.execute("SELECT message::jsonb FROM bus_bus WHERE message::jsonb->>'type'='mp_domain_events'");messages=[r[0] for r in cr.fetchall()]
            self.assertGreater(len(messages),before);self.assertTrue(all(m==dict(type='mp_domain_events',payload=dict(available=True)) for m in messages))

    def test_inverse_producer_commit_order_never_skips_lower_allocated_id(self):
        with self.registry.cursor() as first,self.registry.cursor() as second:
            a=self.env(first)['mp.example.note'].create(dict(title='Lower allocated later committed'));a_id=a.public_id
            b=self.env(second)['mp.example.note'].create(dict(title='Higher allocated first committed'));b_id=b.public_id
            first.execute('SELECT id FROM mp_outbox WHERE aggregate_id=%s',[a_id]);lower=first.fetchone()[0]
            second.execute('SELECT id FROM mp_outbox WHERE aggregate_id=%s',[b_id]);higher=second.fetchone()[0];self.assertLess(lower,higher)
            second.commit()
            batch=self.request('poll',subscription_id=self.sub,limit=50)['deliveries'];self.assertEqual([i['event']['aggregate_id'] for i in batch],[b_id]);self.ack(self.sub,batch)
            first.commit()
            batch=self.request('poll',subscription_id=self.sub,limit=50)['deliveries'];self.assertEqual([i['event']['aggregate_id'] for i in batch],[a_id])

    def test_concurrent_native_consumers_commit_one_original_user_effect(self):
        a=self.subscribe('org.example.notes_labels');b=self.subscribe('org.example.notes_labels');note=self.note();barrier=threading.Barrier(2)
        def run(ident):barrier.wait(timeout=10);return self.consume(ident)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[a,b]))
        self.assertEqual(sorted(r['state'] for r in results),['applied','duplicate'])
        with self.registry.cursor() as cr:
            row=self.env(cr)['mp.example.note.event.summary'].search([('note_id','=',note)])
            self.assertEqual(len(row),1);self.assertEqual((row.event_count,row.last_revision,row.write_uid.id),(1,1,FIXTURE['users']['alice']['id']))
        event=self.event(note)[0]
        for ident in [a,b]:
            self.request('replay',subscription_id=ident,event_ids=[event['public_id']]);self.assertEqual(self.consume(ident)['state'],'duplicate')
        with self.registry.cursor() as cr:self.assertEqual(self.env(cr)['mp.example.note.event.summary'].search([('note_id','=',note)]).event_count,1)

    def test_consumer_failure_rolls_back_effect_and_receipt_not_producer(self):
        sub=self.subscribe('org.example.notes_labels');note=self.note();original=events.CONSUMERS[HANDLER]
        def fail(env,event,bound):original.apply(env,event,bound);raise RuntimeError('Synthetic private failure')
        events.CONSUMERS[HANDLER]=replace(original,apply=fail)
        try:self.assertEqual(self.consume(sub)['state'],'retry')
        finally:events.CONSUMERS[HANDLER]=original
        self.assertEqual(len(self.event(note)),1)
        with self.registry.cursor() as cr:
            self.assertEqual(self.env(cr)['mp.example.note.event.summary'].search_count([('note_id','=',note)]),0)
            cr.execute('SELECT count(*) FROM mp_event_consumption c JOIN mp_outbox o ON o.id=c.event_id WHERE o.aggregate_id=%s',[note]);self.assertEqual(cr.fetchone()[0],0)
            cr.execute("UPDATE mp_event_delivery SET available_at=timezone('UTC',clock_timestamp()) WHERE subscription_id=(SELECT id FROM mp_event_subscription WHERE public_id=%s)",[sub]);cr.commit()
        self.assertEqual(self.consume(sub)['state'],'applied')

    def test_late_consumer_ack_rolls_back_native_effect_and_dedup(self):
        sub=self.subscribe('org.example.notes_labels');note=self.note();original=events.CONSUMERS[HANDLER]
        def slow(env,event,bound):
            original.apply(env,event,bound);env.flush_all()
            env.cr.execute("UPDATE mp_event_delivery SET lease_until=timezone('UTC',clock_timestamp())+interval '0.05 second' WHERE event_id=(SELECT id FROM mp_outbox WHERE public_id=%s) AND subscription_id=(SELECT id FROM mp_event_subscription WHERE public_id=%s)",[event['id'],sub]);env.cr.execute('SELECT pg_sleep(0.1)')
        events.CONSUMERS[HANDLER]=replace(original,apply=slow)
        try:self.assertEqual(self.consume(sub)['state'],'claim_lost')
        finally:events.CONSUMERS[HANDLER]=original
        with self.registry.cursor() as cr:
            self.assertEqual(self.env(cr)['mp.example.note.event.summary'].search_count([('note_id','=',note)]),0)
            cr.execute('SELECT count(*) FROM mp_event_consumption c JOIN mp_outbox o ON o.id=c.event_id WHERE o.aggregate_id=%s',[note]);self.assertEqual(cr.fetchone()[0],0)

    def test_expired_receipt_reclaims_and_obsolete_ack_conflicts(self):
        self.note();old=self.request('poll',subscription_id=self.sub,limit=50)['deliveries']
        with self.registry.cursor() as cr:cr.execute("UPDATE mp_event_delivery SET lease_until=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[old[0]['id']]);cr.commit()
        self.assertEqual(self.request('poll',subscription_id=self.sub,limit=50)['deliveries'],[])
        with self.registry.cursor() as cr:cr.execute("UPDATE mp_event_delivery SET available_at=timezone('UTC',clock_timestamp()) WHERE public_id=%s",[old[0]['id']]);cr.commit()
        new=self.request('poll',subscription_id=self.sub,limit=50)['deliveries'];self.assertEqual(len(new),1);self.assertGreater(new[0]['generation'],old[0]['generation'])
        with self.assertRaises(PublicError) as error:self.ack(self.sub,old)
        self.assertEqual(error.exception.code,'CONFLICT');self.ack(self.sub,new);self.ack(self.sub,new)

    def test_dead_letter_status_and_three_explicit_replays_are_bounded(self):
        note=self.note();items=self.request('poll',subscription_id=self.sub,limit=50)['deliveries'];delivery=items[0]['id']
        for _ in range(5):
            with self.registry.cursor() as cr:cr.execute("UPDATE mp_event_delivery SET lease_until=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[delivery]);cr.commit()
            self.request('poll',subscription_id=self.sub,limit=50)
            with self.registry.cursor() as cr:cr.execute("UPDATE mp_event_delivery SET available_at=timezone('UTC',clock_timestamp()) WHERE public_id=%s",[delivery]);cr.commit()
            self.request('poll',subscription_id=self.sub,limit=50)
        status=self.request('status',subscription_id=self.sub);row=next(r for r in status['deliveries'] if r['id']==delivery)
        self.assertEqual((row['state'],row['attempts'],row['error_code']),('dead_letter',5,'ACK_EXPIRED'))
        event=self.event(note)[0]['public_id']
        for _ in range(3):self.request('replay',subscription_id=self.sub,event_ids=[event])
        with self.assertRaises(PublicError) as error:self.request('replay',subscription_id=self.sub,event_ids=[event])
        self.assertEqual(error.exception.code,'CONFLICT')

    def test_foreign_subscription_topic_binding_and_payload_scope_fail(self):
        self.note();foreign=self.note(actor='bob',workspace='B')
        with self.assertRaises(PublicError) as error:self.request('poll',subscription_id=self.sub,limit=50,workspace='B')
        self.assertEqual(error.exception.code,'NOT_FOUND')
        items=self.request('poll',subscription_id=self.sub,limit=50)['deliveries'];self.assertTrue(items);self.assertNotIn(foreign,[i['event']['aggregate_id'] for i in items])
        with self.assertRaises(PublicError) as error:self.request('replay',subscription_id=self.sub,event_ids=[self.event(foreign)[0]['public_id']])
        self.assertEqual(error.exception.code,'NOT_FOUND')

    def test_current_membership_feature_grant_and_binding_rechecked(self):
        sub=self.subscribe('org.example.notes_labels');self.note();workspace=FIXTURE['workspaces']['A']['id']
        with self.registry.cursor() as cr:cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']]);actor=cr.fetchone()[0]
        cases=[
            ('UPDATE mp_membership SET state=%s WHERE principal_id=%s AND workspace_id=%s',['revoked',actor,workspace],['active',actor,workspace]),
            ("UPDATE mp_workspace_plugin SET availability=%s WHERE plugin_id='org.example.notes' AND workspace_id=%s",['suspended',workspace],['enabled',workspace]),
            ("UPDATE mp_plugin_grant SET state=%s WHERE workspace_id=%s AND capability='org.example.notes:notes.read' AND installation_id=(SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels')",['revoked',workspace],['approved',workspace]),
            ("UPDATE mp_service_binding SET state=%s WHERE workspace_id=%s AND alias='documents' AND consumer_id=(SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels')",['unavailable',workspace],['active',workspace]),
        ]
        for query,new,old in cases:
            with self.subTest(table=query.split()[1]),self.changed(query,new,old):
                for operation,args in [('poll',dict(limit=50)),('status',{}),('replay',dict(event_ids=[str(uuid4())]))]:
                    with self.assertRaises((AccessError,PublicError)):self.request(operation,subscription_id=sub,**args)

    def test_role_downgrade_blocks_native_projection_before_claim(self):
        sub=self.subscribe('org.example.notes_labels');note=self.note();space=FIXTURE['workspaces']['A']['id']
        query="UPDATE mp_membership SET role=%s WHERE workspace_id=%s AND principal_id=(SELECT id FROM mp_principal WHERE public_id=%s)"
        with self.changed(query,['viewer',space,FIXTURE['users']['alice']['principal_id']],['administrator',space,FIXTURE['users']['alice']['principal_id']]):
            with self.assertRaises(AccessError):self.consume(sub)
        with self.registry.cursor() as cr:self.assertEqual(self.env(cr)['mp.example.note.event.summary'].search_count([('note_id','=',note)]),0)

    def test_subscription_expiry_and_event_retention_refuse_replay(self):
        note=self.note();event=self.event(note)[0]
        with self.registry.cursor() as cr:cr.execute("UPDATE mp_outbox SET occurred_at=timezone('UTC',clock_timestamp())-interval '8 days' WHERE id=%s",[event['id']]);cr.commit()
        self.assertEqual(self.request('poll',subscription_id=self.sub,limit=50)['deliveries'],[])
        with self.assertRaises(PublicError) as error:self.request('replay',subscription_id=self.sub,event_ids=[event['public_id']])
        self.assertEqual(error.exception.code,'NOT_FOUND')
        with self.registry.cursor() as cr:cr.execute("UPDATE mp_event_subscription SET expires_at=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[self.sub]);cr.commit()
        self.assertEqual(self.request('status',subscription_id=self.sub)['state'],'expired')
        with self.assertRaises(PublicError) as error:self.request('poll',subscription_id=self.sub,limit=50)
        self.assertEqual(error.exception.code,'CONFLICT')

    def test_canvas_major2_binding_uses_same_event_contract_without_UI_change(self):
        sub=self.subscribe('org.example.canvas');note=self.note()
        batch=self.request('poll',subscription_id=sub,limit=50)['deliveries'];self.assertEqual(len(batch),1);self.assertEqual(batch[0]['event']['payload']['note_id'],note)
        self.assertEqual(batch[0]['event']['schema_version'],1)

    def test_additional_subscription_idempotency_and_binding_epoch(self):
        key=str(uuid4())
        with self.registry.cursor() as cr:
            binding=self.binding(cr,'org.example.notes_labels')
            def create():return events.dispatch(self.env(cr),dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=key),binding_id=binding)
            a=create();b=create();self.assertEqual(a,b);cr.commit()
        sub=a['subscription_id'];self.subs.append(sub)
        with self.assertRaises(PublicError) as error:self.request('poll',actor='operator',subscription_id=sub,limit=50)
        self.assertEqual(error.exception.code,'NOT_FOUND')
        with self.registry.cursor() as cr:cr.execute('SELECT descriptor FROM mp_service_binding WHERE public_id=%s',[binding]);original=cr.fetchone()[0]
        changed=dict(original,generation=original['generation']+1)
        query='UPDATE mp_service_binding SET descriptor=%s::jsonb WHERE public_id=%s'
        with self.changed(query,[json.dumps(changed),binding],[json.dumps(original),binding]):
            with self.registry.cursor() as cr:
                with self.assertRaises(PublicError) as error:events.dispatch(self.env(cr),dict(protocol=1,kind='poll_request',request_id=str(uuid4()),subscription_id=sub,limit=50))
                self.assertEqual(error.exception.code,'CONFLICT')
                with self.assertRaises(PublicError) as error:create()
                self.assertEqual(error.exception.code,'CONFLICT')

    def test_technical_credentials_origin_and_consumer_scope_intersection(self):
        credentials=[];worker=FIXTURE['users']['worker'];workspace=FIXTURE['workspaces']['A']['id']
        with self.registry.cursor() as cr:
            cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[worker['principal_id']]);principal=cr.fetchone()[0]
            cr.execute("SELECT plugin_id,public_id FROM mp_plugin_installation WHERE plugin_id IN ('org.example.notes','org.example.notes_labels')");installations=dict(cr.fetchall())
            def provision(plugin):
                row=api.Environment(cr,1,{})['mp.service.credential'].create(dict(name='Owned event credential',principal_id=principal,workspace_id=workspace,token_digest=hashlib.sha256(uuid4().bytes).hexdigest(),installation_public_id=installations[plugin],actions='read',expires_at=fields.Datetime.add(fields.Datetime.now(),minutes=5)))
                credentials.append(row.id);return row.id
            label_credential=provision('org.example.notes_labels');note_credential=provision('org.example.notes');cr.commit()
        try:
            with self.assertRaises(AccessError):self.subscribe(actor='worker')
            sub=self.subscribe(actor='worker',credential=label_credential);note=self.note()
            items=self.request('poll',actor='worker',credential=label_credential,subscription_id=sub,limit=50)['deliveries'];self.assertEqual([d['event']['aggregate_id'] for d in items],[note]);self.ack(sub,items,actor='worker',credential=label_credential)
            grant="UPDATE mp_plugin_grant SET state=%s WHERE workspace_id=%s AND capability='org.example.notes:notes.read' AND installation_id=(SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels')"
            with self.changed(grant,['revoked',workspace],['approved',workspace]):
                with self.assertRaises(AccessError):self.request('poll',actor='worker',credential=label_credential,subscription_id=sub,limit=50)
                # Nominating the provider's own binding cannot bypass the
                # authenticated technical origin's missing integration grant.
                with self.assertRaises(AccessError):self.subscribe('org.example.notes',actor='worker',credential=label_credential)
            role='UPDATE mp_membership SET role=%s WHERE principal_id=%s AND workspace_id=%s'
            with self.changed(role,['editor',principal,workspace],['viewer',principal,workspace]):
                with self.registry.cursor() as cr:cr.execute("UPDATE mp_service_credential SET actions='read,create,write' WHERE id=ANY(%s)",[credentials]);cr.commit()
                native_sub=self.subscribe('org.example.notes_labels',actor='worker',credential=label_credential);target=self.note()
                with self.registry.cursor() as cr:
                    native=self.env(cr,'worker',credential=label_credential)
                    result=retrying(lambda:events.consume_registered(native,native_sub,HANDLER),native);self.assertEqual(result['state'],'applied')
                with self.registry.cursor() as cr:self.assertEqual(self.env(cr)['mp.example.note.event.summary'].search([('note_id','=',target)]).write_uid.id,worker['id'])
                wrong_origin=self.subscribe('org.example.notes_labels',actor='worker',credential=note_credential)
                with self.registry.cursor() as cr:
                    with self.assertRaises(AccessError):events.consume_registered(self.env(cr,'worker',credential=note_credential),wrong_origin,HANDLER)
                with self.registry.cursor() as cr:cr.execute("UPDATE mp_service_credential SET actions='read' WHERE id=%s",[label_credential]);cr.commit()
                with self.registry.cursor() as cr:
                    with self.assertRaises(AccessError):events.consume_registered(self.env(cr,'worker',credential=label_credential),native_sub,HANDLER)
            with self.registry.cursor() as cr:cr.execute("UPDATE mp_service_credential SET expires_at=timezone('UTC',clock_timestamp())-interval '1 second' WHERE id=%s",[label_credential]);cr.commit()
            with self.assertRaises(AccessError):self.request('poll',actor='worker',credential=label_credential,subscription_id=sub,limit=50)
        finally:
            with self.registry.cursor() as cr:cr.execute("UPDATE mp_service_credential SET state='revoked' WHERE id=ANY(%s)",[credentials]);cr.commit()
