"""Current installed native authority matrix, all fixture writes rolled back."""
import hashlib,json,unittest
from dataclasses import replace
from uuid import uuid4
from odoo import api,fields
from odoo.exceptions import AccessError,MissingError
from odoo.addons.mp_identity.scopes import scoped_environment,resolve_scope
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core import job_dispatch as jobs


class CurrentJobGuards(unittest.TestCase):
    def observe(self):
        result={}
        for table in ['mp_job','mp_example_note','mp_outbox','mp_membership','mp_workspace_plugin','mp_plugin_grant','mp_service_binding','mp_service_credential']:
            self.cr.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id');result[table]=self.cr.fetchall()
        for name,query in [('principals','SELECT id,state,kind,user_id FROM mp_principal ORDER BY id'),('users','SELECT id,active FROM res_users ORDER BY id'),('groups','SELECT uid,gid FROM res_groups_users_rel ORDER BY uid,gid'),('control','SELECT to_jsonb(t) FROM mp_dispatch_control t')]:
            self.cr.execute(query);result[name]=self.cr.fetchall()
        return result

    def native(self,workspace='C',user='alice',consumer=None,credential=None):
        actor=FIXTURE['users'][user];space=FIXTURE['workspaces'][workspace]
        native=scoped_environment(api.Environment(self.cr,actor['id'],{}),space['public_id'])
        plugin='org.example.notes_labels' if consumer==self.labels else 'org.example.notes'
        installation=consumer or FIXTURE['bindings'][workspace]['consumer_installation_id']
        if credential:
            scope=replace(resolve_scope(native,space['public_id']),credential_id=credential,allowed_actions=frozenset({'read'}))
            native=native(context={**native.context,'_mp_scope':resolve_scope(native,space['public_id'],previous=scope)})
        return native(context={**native.context,'_mp_call_frame':CallFrame(actor['principal_id'],space['public_id'],FIXTURE['site_id'],installation,plugin,())})

    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr;self.before=self.observe()
        self.cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels' AND state='installed'");self.labels=self.cr.fetchone()[0]
        self.env=self.native();self.note=self.env['mp.example.note'].create(dict(title='Current   authority   '+uuid4().hex));self.title=self.note.title
        self.actor=self.env.context['_mp_scope'].principal_id;self.workspace=FIXTURE['workspaces']['C']['id']

    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(self.observe(),self.before);self.cr.rollback()

    def enqueue(self,method='normalize_title',native=None,note=None,key=None):
        note=note or self.note
        return jobs.enqueue_bound(native or self.env,'documents','org.example.notes:'+method,dict(note_id=note.public_id,expected_revision=note.revision),key or uuid4().hex)

    def prepare(self):return jobs.prepare_one(ENV,str(uuid4()))
    def finish(self,invocation):return jobs.finish_one(ENV,invocation,jobs.compute(invocation))
    def row(self,ident):
        self.cr.execute('SELECT to_jsonb(t) FROM mp_job t WHERE public_id=%s',[ident]);return self.cr.fetchone()[0]
    def denied(self,value,ident,code='FORBIDDEN'):
        self.assertEqual(value,dict(job_id=ident,state='dead_letter',error_code=code))
        self.cr.execute('SELECT title,revision FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone(),(self.title,1))

    def test_duplicate_retains_first_trace_and_original_actor(self):
        key=uuid4().hex;ident=self.enqueue(key=key);row=self.row(ident)
        self.assertEqual(self.enqueue(key=key),ident);self.assertEqual(self.row(ident)['payload'],row['payload'])
        invocation=self.prepare();self.assertEqual(invocation.database,self.cr.dbname)
        result=self.finish(invocation);self.assertEqual(result,dict(note_id=self.note.public_id,revision=2,changed=True))
        self.cr.execute('SELECT write_uid,revision FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone(),(FIXTURE['users']['alice']['id'],2))

    def test_principal_user_membership_before_claim(self):
        variants=[('UPDATE mp_principal SET state=%s WHERE id=%s',['suspended',self.actor],['active',self.actor]),
            ('UPDATE res_users SET active=%s WHERE id=%s',[False,FIXTURE['users']['alice']['id']],[True,FIXTURE['users']['alice']['id']]),
            ('UPDATE mp_membership SET state=%s WHERE principal_id=%s AND workspace_id=%s',['revoked',self.actor,self.workspace],['active',self.actor,self.workspace])]
        for query,new,old in variants:
            ident=self.enqueue();self.cr.execute(query,new)
            try:self.denied(self.prepare(),ident)
            finally:self.cr.execute(query,old)

    def test_role_between_compute_and_apply(self):
        ident=self.enqueue();invocation=self.prepare();computed=jobs.compute(invocation)
        self.cr.execute("UPDATE mp_membership SET role='viewer' WHERE principal_id=%s AND workspace_id=%s",[self.actor,self.workspace])
        self.denied(jobs.finish_one(ENV,invocation,computed),ident)

    def test_feature_binding_installation_between_compute_and_apply(self):
        installation=FIXTURE['bindings']['C']['provider_installation_id']
        variants=[("UPDATE mp_workspace_plugin SET availability=%s WHERE workspace_id=%s AND plugin_id='org.example.notes'",['suspended',self.workspace],['enabled',self.workspace],'PLUGIN_SUSPENDED'),
            ("UPDATE mp_service_binding SET state=%s WHERE public_id=%s",['unavailable',FIXTURE['bindings']['C']['binding_id']],['active',FIXTURE['bindings']['C']['binding_id']],'DEPENDENCY_UNAVAILABLE'),
            ('UPDATE mp_plugin_installation SET state=%s WHERE public_id=%s',['suspended',installation],['installed',installation],'PLUGIN_SUSPENDED')]
        for query,new,old,code in variants:
            ident=self.enqueue();invocation=self.prepare();self.cr.execute(query,new)
            try:self.denied(self.finish(invocation),ident,code)
            finally:self.cr.execute(query,old)

    def test_feature_binding_installation_before_claim(self):
        installation=FIXTURE['bindings']['C']['provider_installation_id']
        variants=[("UPDATE mp_workspace_plugin SET availability=%s WHERE workspace_id=%s AND plugin_id='org.example.notes'",['suspended',self.workspace],['enabled',self.workspace],'PLUGIN_SUSPENDED'),
            ('UPDATE mp_service_binding SET state=%s WHERE public_id=%s',['unavailable',FIXTURE['bindings']['C']['binding_id']],['active',FIXTURE['bindings']['C']['binding_id']],'DEPENDENCY_UNAVAILABLE'),
            ('UPDATE mp_plugin_installation SET state=%s WHERE public_id=%s',['suspended',installation],['installed',installation],'PLUGIN_SUSPENDED')]
        for query,new,old,code in variants:
            ident=self.enqueue();self.cr.execute(query,new)
            try:self.denied(self.prepare(),ident,code)
            finally:self.cr.execute(query,old)

    def test_integration_grant_before_claim(self):
        native=self.native(workspace='A',consumer=self.labels);note=native['mp.example.note'].create(dict(title='Read integration guard'))
        ident=self.enqueue('inspect_revision',native=native,note=note)
        self.cr.execute("UPDATE mp_plugin_grant SET state='revoked' WHERE installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s) AND workspace_id=%s AND capability='org.example.notes:notes.read'",[self.labels,FIXTURE['workspaces']['A']['id']])
        self.denied(self.prepare(),ident)

    def technical(self):
        worker=FIXTURE['users']['worker'];self.cr.execute('SELECT id FROM mp_principal WHERE user_id=%s',[worker['id']]);principal=self.cr.fetchone()[0]
        credential=ENV['mp.service.credential'].create(dict(name='Rollback-only current job guard',principal_id=principal,workspace_id=FIXTURE['workspaces']['A']['id'],token_digest=hashlib.sha256(uuid4().bytes).hexdigest(),installation_public_id=FIXTURE['bindings']['A']['consumer_installation_id'],actions='read',expires_at=fields.Datetime.add(fields.Datetime.now(),minutes=5)))
        return credential,self.native(workspace='A',user='worker',credential=credential.id)

    def test_technical_origin_without_scoped_credential_denied(self):
        native=self.native(workspace='A',user='worker')
        note=self.native(workspace='A')['mp.example.note'].create(dict(title='Technical no credential'))
        with self.assertRaises(AccessError):self.enqueue('inspect_revision',native=native,note=note)

    def test_technical_credential_revoked_before_claim(self):
        credential,native=self.technical();note=self.native(workspace='A')['mp.example.note'].create(dict(title='Technical credential revocation'))
        ident=self.enqueue('inspect_revision',native=native,note=note);credential.write(dict(state='revoked'))
        self.denied(self.prepare(),ident)

    def test_technical_credential_expired_before_claim(self):
        credential,native=self.technical();note=self.native(workspace='A')['mp.example.note'].create(dict(title='Technical credential expiry'))
        ident=self.enqueue('inspect_revision',native=native,note=note)
        credential.write(dict(expires_at=fields.Datetime.subtract(fields.Datetime.now(),minutes=1)))
        self.denied(self.prepare(),ident)

    def test_technical_native_administrator_mapping_denied(self):
        _,native=self.technical();note=self.native(workspace='A')['mp.example.note'].create(dict(title='No technical administrator'))
        self.cr.execute("INSERT INTO res_groups_users_rel(uid,gid) SELECT %s,res_id FROM ir_model_data WHERE model='res.groups' AND module='base' AND name='group_system' ON CONFLICT DO NOTHING",[FIXTURE['users']['worker']['id']])
        with self.assertRaises(AccessError):self.enqueue('inspect_revision',native=native,note=note)

    def test_resource_revision_cas_blocks_old_computation(self):
        ident=self.enqueue();invocation=self.prepare();computed=jobs.compute(invocation)
        self.note.with_context(expected_revision=1).write(dict(body='New user revision'))
        self.assertEqual(jobs.finish_one(ENV,invocation,computed),dict(job_id=ident,state='dead_letter',error_code='CONFLICT'))
        self.cr.execute('SELECT title,body,revision FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone(),(self.title,'New user revision',2))

    def test_status_same_workspace_other_actor_and_current_revocation(self):
        ident=self.enqueue('inspect_revision');self.finish(self.prepare())
        self.cr.execute('SELECT id FROM mp_principal WHERE user_id=%s',[FIXTURE['users']['bob']['id']]);bob=self.cr.fetchone()[0]
        ENV['mp.membership'].create(dict(principal_id=bob,workspace_id=self.workspace,role='viewer',state='active'))
        for native in [self.native(user='bob'),self.native(workspace='A')]:
            with self.assertRaises(PublicError) as error:jobs.status(native,ident)
            self.assertEqual(error.exception.code,'NOT_FOUND')
        self.assertEqual(jobs.status(self.env,ident)['state'],'completed')
        self.cr.execute("UPDATE mp_membership SET state='revoked' WHERE principal_id=%s AND workspace_id=%s",[self.actor,self.workspace])
        with self.assertRaises(AccessError):jobs.status(self.env,ident)
