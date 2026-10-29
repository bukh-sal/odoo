"""Actual original-user job dispatch tests on the owned F-01b PostgreSQL site."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib,json,unittest
from uuid import uuid4
from odoo import api,fields
from odoo.exceptions import AccessError,MissingError
from odoo.addons.mp_identity.scopes import scoped_environment,resolve_scope
from odoo.addons.mp_core.dispatch import CallFrame,call_bound
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import durable as queue
from modular_platform.contracts import ContractError


class AuthorizedJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=ENV.registry;cls.fixture=FIXTURE;cls.site=FIXTURE['site_id']
        cls.A=FIXTURE['workspaces']['A'];cls.B=FIXTURE['workspaces']['B'];cls.alice=FIXTURE['users']['alice'];cls.owned=[]
        with cls.registry.cursor() as cr:
            assert cr.dbname.startswith('mp_disposable_r0_r1_g6_')
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");assert cr.fetchone()[0]==cls.site
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");cls.release=cr.fetchone()[0]
            cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[cls.alice['principal_id']]);cls.actor=cr.fetchone()[0]
            cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes' AND state='installed'");cls.consumer=cr.fetchone()[0]
            cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels' AND state='installed'");cls.labels=cr.fetchone()[0]
            queue.set_control(cr,cls.site,cls.release,'enabled');cr.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.registry.cursor() as cr:
            queue.set_control(cr,cls.site,cls.release,'paused')
            cr.execute("UPDATE mp_job SET state='held',lease_owner=NULL,lease_until=NULL WHERE public_id=ANY(%s) AND state IN ('pending','retry','running')",[cls.owned]);cr.commit()

    def setUp(self):
        with self.registry.cursor() as cr:
            queue.set_control(cr,self.site,self.release,'enabled')
            note=self.native(cr)['mp.example.note'].create(dict(title='Job   authorization  '+uuid4().hex,body='Minimal synthetic job fixture'))
            self.note=note.public_id;self.row_id=note.id;self.title=note.title;cr.commit()

    def tearDown(self):
        with self.registry.cursor() as cr:
            cr.execute("UPDATE mp_job SET state='held',lease_owner=NULL,lease_until=NULL WHERE public_id=ANY(%s) AND state IN ('pending','retry','running')",[self.owned]);cr.commit()

    def native(self,cr,*,user=None,workspace=None,consumer=None,credential=None):
        user=user or self.alice;workspace=workspace or self.A
        native=scoped_environment(api.Environment(cr,user['id'],{}),workspace['public_id'])
        if credential:
            scope=replace(resolve_scope(native,workspace['public_id']),credential_id=credential,allowed_actions=frozenset({'read','write'}))
            native=native(context={'_mp_scope':resolve_scope(native,workspace['public_id'],previous=scope)})
        plugin='org.example.notes_labels' if consumer==self.labels else 'org.example.notes'
        return native(context={**native.context,'_mp_call_frame':CallFrame(user['principal_id'],workspace['public_id'],self.site,consumer or self.consumer,plugin,())})

    def enqueue(self,*,method='normalize_title',values=None,key=None,**scope):
        with self.registry.cursor() as cr:
            ident=jobs.enqueue_bound(self.native(cr,**scope),'documents','org.example.notes:'+method,values or dict(note_id=self.note,expected_revision=1),key or uuid4().hex)
            cr.commit();self.owned.append(ident);return ident

    def prepare(self,lease_seconds=30):
        with self.registry.cursor() as cr:
            result=jobs.prepare_one(api.Environment(cr,1,{}),str(uuid4()),lease_seconds=lease_seconds);cr.commit();return result

    def finish(self,invocation):
        computed=jobs.compute(invocation)
        with self.registry.cursor() as cr:
            result=jobs.finish_one(api.Environment(cr,1,{}),invocation,computed);cr.commit();return result

    def record(self,ident):
        with self.registry.cursor() as cr:
            cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident]);return cr.fetchone()[0]

    def business(self):
        with self.registry.cursor() as cr:
            cr.execute('SELECT title,revision,write_uid FROM mp_example_note WHERE id=%s',[self.row_id]);return cr.fetchone()

    @contextmanager
    def changed(self,query,parameters,restore,old_parameters):
        with self.registry.cursor() as cr:cr.execute(query,parameters);cr.commit()
        try:yield
        finally:
            with self.registry.cursor() as cr:cr.execute(restore,old_parameters);cr.commit()

    def assert_denied(self,ident,result,code='FORBIDDEN'):
        self.assertEqual(result,dict(job_id=ident,state='dead_letter',error_code=code))
        self.assertEqual(self.business()[:2],(self.title,1))

    def test_normalization_uses_original_native_user_and_safe_status(self):
        ident=self.enqueue();invocation=self.prepare();self.assertIsInstance(invocation,jobs.Invocation)
        result=self.finish(invocation)
        self.assertEqual(result,dict(note_id=self.note,revision=2,changed=True))
        self.assertEqual(self.business(),(' '.join(self.title.split()),2,self.alice['id']))
        with self.registry.cursor() as cr:
            value=jobs.status(self.native(cr),ident)
            self.assertEqual(value['result'],result);self.assertEqual(value['state'],'completed');self.assertEqual(value['attempts'],1)
            self.assertEqual(set(value),{'id','state','progress','attempts','error_code','result'})
            synchronous=call_bound(self.native(cr),'documents','get',dict(note_id=self.note))
            self.assertEqual(synchronous['title'],self.business()[0]);self.assertEqual(synchronous['revision'],2)

    def test_semantic_dedup_preserves_first_trace_and_rejects_changed_input(self):
        key=uuid4().hex;first=str(uuid4());second=str(uuid4())
        with self.registry.cursor() as cr:
            native=self.native(cr);values=dict(note_id=self.note,expected_revision=1)
            ident=jobs.enqueue_bound(native,'documents','org.example.notes:inspect_revision',values,key,request_id=first)
            again=jobs.enqueue_bound(native,'documents','org.example.notes:inspect_revision',values,key,request_id=second)
            self.assertEqual(ident,again);cr.commit();self.owned.append(ident)
        self.assertEqual(self.record(ident)['payload']['context']['request_id'],first)
        with self.registry.cursor() as cr:
            native=self.native(cr);other=native['mp.example.note'].create(dict(title='Other note'))
            with self.assertRaises(queue.QueueError):
                jobs.enqueue_bound(native,'documents','org.example.notes:inspect_revision',dict(note_id=other.public_id,expected_revision=1),key)
            cr.rollback()
        invocation=self.prepare();self.assertEqual(self.finish(invocation),dict(note_id=self.note,revision=1))

    def test_foreign_and_missing_records_share_not_found(self):
        with self.registry.cursor() as cr:
            foreign=self.native(cr,user=FIXTURE['users']['bob'],workspace=self.B)['mp.example.note'].create(dict(title='Foreign B note'));foreign_id=foreign.public_id;cr.commit()
        for ident in [foreign_id,str(uuid4())]:
            with self.subTest(resource=ident==foreign_id),self.registry.cursor() as cr:
                with self.assertRaises(MissingError) as error:jobs.enqueue_bound(self.native(cr),'documents','org.example.notes:inspect_revision',dict(note_id=ident,expected_revision=1),uuid4().hex)
                self.assertEqual(str(error.exception),'Resource unavailable');cr.rollback()

    def test_payload_cannot_supply_actor_role_user_site_or_consumer(self):
        for field,value in [('actor_id',1),('user_id',1),('role','administrator'),('site_id',self.site),('consumer_installation_id',self.consumer)]:
            with self.subTest(field=field),self.registry.cursor() as cr:
                with self.assertRaises(ContractError):jobs.enqueue_bound(self.native(cr),'documents','org.example.notes:inspect_revision',dict(note_id=self.note,expected_revision=1,**{field:value}),uuid4().hex)
                cr.rollback()

    def test_viewer_cannot_write_but_can_read_own_workspace(self):
        with self.registry.cursor() as cr:
            note=self.native(cr,user=FIXTURE['users']['bob'],workspace=self.B)['mp.example.note'].create(dict(title='Viewer read proof'));ident=note.public_id;cr.commit()
        with self.assertRaises(AccessError):self.enqueue(workspace=self.B,values=dict(note_id=ident,expected_revision=1))
        job=self.enqueue(method='inspect_revision',workspace=self.B,values=dict(note_id=ident,expected_revision=1))
        self.assertEqual(self.finish(self.prepare()),dict(note_id=ident,revision=1));self.assertEqual(self.record(job)['state'],'completed')

    def test_current_membership_principal_and_user_rechecked_before_claim(self):
        matrices=[
            ("UPDATE mp_membership SET state=%s WHERE principal_id=%s AND workspace_id=%s",['revoked',self.actor,self.A['id']],['active',self.actor,self.A['id']]),
            ("UPDATE mp_principal SET state=%s WHERE id=%s",['suspended',self.actor],['active',self.actor]),
            ("UPDATE res_users SET active=%s WHERE id=%s",[False,self.alice['id']],[True,self.alice['id']]),
        ]
        for query,new,old in matrices:
            with self.subTest(table=query.split()[1]):
                ident=self.enqueue()
                with self.changed(query,new,query,old):self.assert_denied(ident,self.prepare())

    def test_membership_role_revoked_between_compute_and_finalization(self):
        ident=self.enqueue();invocation=self.prepare()
        query='UPDATE mp_membership SET role=%s WHERE principal_id=%s AND workspace_id=%s'
        with self.changed(query,['viewer',self.actor,self.A['id']],query,['administrator',self.actor,self.A['id']]):
            self.assert_denied(ident,self.finish(invocation))

    def test_feature_binding_and_installation_rechecked(self):
        matrices=[
            ("UPDATE mp_workspace_plugin SET availability=%s WHERE workspace_id=%s AND plugin_id=%s",['suspended',self.A['id'],'org.example.notes'],['enabled',self.A['id'],'org.example.notes'],'PLUGIN_SUSPENDED'),
            ("UPDATE mp_service_binding SET state=%s WHERE workspace_id=%s AND consumer_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s) AND alias='documents'",['unavailable',self.A['id'],self.consumer],['active',self.A['id'],self.consumer],'DEPENDENCY_UNAVAILABLE'),
            ("UPDATE mp_plugin_installation SET state=%s WHERE public_id=%s",['suspended',self.consumer],['installed',self.consumer],'PLUGIN_SUSPENDED'),
        ]
        for query,new,old,code in matrices:
            with self.subTest(table=query.split()[1]):
                ident=self.enqueue();invocation=self.prepare()
                with self.changed(query,new,query,old):self.assert_denied(ident,self.finish(invocation),code)

    def test_integration_grant_rechecked_before_dispatch(self):
        ident=self.enqueue(method='inspect_revision',consumer=self.labels)
        query="UPDATE mp_plugin_grant SET state=%s WHERE workspace_id=%s AND installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s) AND capability='org.example.notes:notes.read'"
        with self.changed(query,['revoked',self.A['id'],self.labels],query,['approved',self.A['id'],self.labels]):self.assert_denied(ident,self.prepare())

    def test_resource_revision_change_conflicts_without_overwriting(self):
        ident=self.enqueue();invocation=self.prepare()
        with self.registry.cursor() as cr:
            self.native(cr)['mp.example.note'].browse(self.row_id).with_context(expected_revision=1).write(dict(title='User edited after computation'));cr.commit()
        self.assertEqual(self.finish(invocation),dict(job_id=ident,state='dead_letter',error_code='CONFLICT'))
        self.assertEqual(self.business()[:2],('User edited after computation',2))

    def test_status_requires_current_actor_workspace_resource_and_authority(self):
        ident=self.enqueue(method='inspect_revision');self.finish(self.prepare())
        for user,workspace in [(FIXTURE['users']['operator'],self.A),(self.alice,self.B)]:
            with self.subTest(user=user['id'],workspace=workspace['public_id']),self.registry.cursor() as cr:
                with self.assertRaises(PublicError) as error:jobs.status(self.native(cr,user=user,workspace=workspace),ident)
                self.assertEqual(error.exception.code,'NOT_FOUND')
        query='UPDATE mp_membership SET state=%s WHERE principal_id=%s AND workspace_id=%s'
        with self.changed(query,['revoked',self.actor,self.A['id']],query,['active',self.actor,self.A['id']]),self.registry.cursor() as cr:
            with self.assertRaises(AccessError):jobs.status(self.native(cr),ident)

    def test_technical_identity_needs_live_scoped_credential(self):
        worker=FIXTURE['users']['worker']
        with self.assertRaises(AccessError):self.enqueue(method='inspect_revision',user=worker)
        with self.registry.cursor() as cr:
            env=api.Environment(cr,1,{});cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[worker['principal_id']]);principal=cr.fetchone()[0]
            credential=env['mp.service.credential'].create(dict(name='G6 job credential',principal_id=principal,workspace_id=self.A['id'],token_digest=hashlib.sha256(uuid4().bytes).hexdigest(),installation_public_id=self.consumer,actions='read',expires_at=fields.Datetime.add(fields.Datetime.now(),minutes=5)))
            credential_id=credential.id;cr.commit()
        ident=self.enqueue(method='inspect_revision',user=worker,credential=credential_id)
        query='UPDATE mp_service_credential SET state=%s WHERE id=%s'
        with self.changed(query,['revoked',credential_id],query,['active',credential_id]):self.assert_denied(ident,self.prepare())
        # Explicitly retire this suite-owned credential, never leave it usable.
        with self.registry.cursor() as cr:cr.execute(query,['revoked',credential_id]);cr.commit()
