"""Actual installed Notes native batch/CAS regressions; all writes roll back."""
import json,unittest
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame,call_bound
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import dispatch_lifecycle as LC

class NativeBatchTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.release=self.cr.fetchone()[0]
        self.lifecycle=LC.LifecycleScope(FIXTURE['site_id'],self.release);self.before=LC.observe(self.cr,self.lifecycle)
        self.cr.execute('SELECT to_jsonb(n) FROM mp_example_note n ORDER BY id');self.business=self.cr.fetchall()
        self.native=self.actor('alice','C');self.model=self.native['mp.example.note']
    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(LC.observe(self.cr,self.lifecycle),self.before)
        self.cr.execute('SELECT to_jsonb(n) FROM mp_example_note n ORDER BY id');self.assertEqual(self.cr.fetchall(),self.business);self.cr.rollback()
    def actor(self,user,workspace):
        native=scoped_environment(api.Environment(self.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id']);binding=FIXTURE['bindings'][workspace]
        frame=CallFrame(FIXTURE['users'][user]['principal_id'],FIXTURE['workspaces'][workspace]['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
        return native(context={**native.context,'_mp_call_frame':frame})
    def create(self,title='Native batch reference'):
        return self.model.create({'title':title,'body':'Rollback-only minimal test'})
    def rows(self,ident):
        self.cr.execute('SELECT aggregate_sequence,payload FROM mp_outbox WHERE aggregate_id=%s ORDER BY aggregate_sequence',[ident]);return self.cr.fetchall()
    def test_native_multi_create_repeated_batch_write_and_unlink(self):
        records=self.model.create([{'title':'Native batch one'},{'title':'Native batch two'}]);ids=records.ids;public=records.mapped('public_id')
        self.assertEqual(records.mapped('revision'),[1,1])
        records.with_context(expected_revisions={str(i):1 for i in ids}).write({'body':'First pending native batch'})
        records.with_context(expected_revisions={str(i):2 for i in ids}).write({'body':'Second pending native batch'})
        self.assertEqual(records.mapped('revision'),[3,3])
        records.with_context(expected_revisions={str(i):3 for i in ids}).unlink()
        self.cr.execute('SELECT count(*) FROM mp_example_note WHERE id=ANY(%s)',[ids]);self.assertEqual(self.cr.fetchone()[0],0)
        for ident in public:
            events=self.rows(ident);self.assertEqual([r[0] for r in events],[1,2,3,4]);self.assertEqual([r[1]['change'] for r in events],['created','updated','updated','deleted'])
    def test_native_service_pending_update_update_delete(self):
        note=self.create();ident=note.public_id
        note.with_context(expected_revision=1).write({'title':'Native pending revision two'})
        value=self.model._mp_service_update({'note_id':ident,'expected_revision':2,'body':'Bound preflight sees pending native revision'})
        self.assertEqual(value['revision'],3)
        deleted=self.model._mp_service_delete({'note_id':ident,'expected_revision':3});self.assertEqual(deleted,dict(id=ident,deleted=True))
        self.assertEqual([r[0] for r in self.rows(ident)],[1,2,3,4])
    def test_registered_bound_chain_has_same_transaction_revisions(self):
        note=call_bound(self.native,'documents','create',{'title':'Registered bound minimal','body':'Reference'})
        for revision in [1,2]:
            note=call_bound(self.native,'documents','update',{'note_id':note['id'],'expected_revision':revision,'body':'Bound revision '+str(revision+1)})
            self.assertEqual(note['revision'],revision+1)
        self.assertEqual(call_bound(self.native,'documents','delete',{'note_id':note['id'],'expected_revision':3}),dict(id=note['id'],deleted=True))
        self.assertEqual([r[0] for r in self.rows(note['id'])],[1,2,3,4])
    def test_stale_native_batch_rolls_back_whole_attempt(self):
        records=self.model.create([{'title':'Atomic one'},{'title':'Atomic two'}]);public=records.mapped('public_id')
        with self.assertRaises(PublicError):
            with self.cr.savepoint():records.with_context(expected_revisions={str(records[0].id):1,str(records[1].id):99}).write({'title':'Must roll back'})
        records.invalidate_recordset();self.assertEqual(records.mapped('revision'),[1,1]);self.assertEqual(records.mapped('title'),['Atomic one','Atomic two'])
        for ident in public:self.assertEqual([r[0] for r in self.rows(ident)],[1])
    def test_stale_unlink_batch_deletes_no_records_or_events(self):
        records=self.model.create([{'title':'Unlink one'},{'title':'Unlink two'}]);ids=records.ids;public=records.mapped('public_id')
        records.with_context(expected_revisions={str(i):1 for i in ids}).write({'body':'Pending revision two'})
        with self.assertRaises(PublicError):records.with_context(expected_revisions={str(ids[0]):2,str(ids[1]):1}).unlink()
        self.assertEqual(len(records.exists()),2);self.assertEqual(records.mapped('revision'),[2,2])
        for ident in public:self.assertEqual([r[0] for r in self.rows(ident)],[1,2])
    def test_stale_bound_update_and_delete_leave_pending_revision(self):
        note=self.create();ident=note.public_id;note.with_context(expected_revision=1).write({'body':'Pending revision two'})
        for method in ['update','delete']:
            with self.assertRaises(PublicError):call_bound(self.native,'documents',method,{'note_id':ident,'expected_revision':1})
        self.assertEqual(note.revision,2);self.assertEqual([r[0] for r in self.rows(ident)],[1,2])
    def test_missing_or_boolean_native_expected_revision_is_not_CAS(self):
        note=self.create()
        for expected in [None,True,'1',0]:
            with self.assertRaises(PublicError):note.with_context(expected_revision=expected).write({'title':'Not authorized by malformed CAS'})
            with self.assertRaises(PublicError):note.with_context(expected_revision=expected).unlink()
        self.assertEqual(note.revision,1);self.assertEqual([r[0] for r in self.rows(note.public_id)],[1])
    def test_mixed_workspace_batch_and_missing_id_are_equally_denied(self):
        own=self.create();foreign=self.actor('bob','B')['mp.example.note'].create({'title':'Foreign batch reference'})
        for ident in [foreign.id,2147483647]:
            mixed=self.model.browse([own.id,ident])
            with self.assertRaises(AccessError):mixed.read(['title'])
            with self.assertRaises(AccessError):mixed.with_context(expected_revision=1).write({'title':'Foreign denied'})
            with self.assertRaises(AccessError):mixed.with_context(expected_revision=1).unlink()
        self.assertEqual(own.revision,1);self.assertEqual(foreign.revision,1)
    def test_viewer_and_pending_role_demotion_cannot_batch_write(self):
        viewer=self.actor('alice','B')['mp.example.note']
        with self.assertRaises(AccessError):viewer.create([{'title':'Denied viewer batch one'},{'title':'Denied viewer batch two'}])
        records=self.model.create([{'title':'Demotion one'},{'title':'Demotion two'}])
        scope=self.native.context['_mp_scope'];member=ENV['mp.membership'].search([('principal_id','=',scope.principal_id),('workspace_id','=',scope.workspace_id)])
        member.write({'role':'viewer'})
        with self.assertRaises(AccessError):records.with_context(expected_revision=1).write({'title':'Denied pending demotion'})
        with self.assertRaises(AccessError):records.with_context(expected_revision=1).unlink()
        self.cr.execute('SELECT revision FROM mp_example_note WHERE id=ANY(%s)',[records.ids]);self.assertEqual([r[0] for r in self.cr.fetchall()],[1,1])
    def test_ownership_and_author_cannot_be_reassigned_by_batch(self):
        records=self.model.create([{'title':'Ownership one'},{'title':'Ownership two'}])
        for values in [{'workspace_id':FIXTURE['workspaces']['B']['id']},{'author_id':FIXTURE['users']['bob']['id']},{'public_id':str(uuid4())}]:
            with self.assertRaises(AccessError):records.with_context(expected_revision=1).write(values)
        self.assertEqual(records.mapped('revision'),[1,1])
