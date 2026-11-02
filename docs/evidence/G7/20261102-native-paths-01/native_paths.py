"""Installed ID03 boundary cases; each test rolls back all fixture changes."""
import hashlib,time,unittest
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.tools.misc import limited_field_access_token

class NativePathTests(unittest.TestCase):
    def observe(self):
        result={}
        for table in ['mp_example_note','mp_outbox','mp_job','ir_attachment','res_groups_users_rel']:
            self.cr.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text');result[table]=self.cr.fetchall()
        return result
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr;self.before=self.observe()
        self.a=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
        self.b=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['B']['public_id'])
        self.own=self.a['mp.example.note'].create({'title':'ID03 rollback '+uuid4().hex,'body':'Private native boundary fixture'})
        self.cr.execute('SELECT id,title FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces']['B']['id']]);self.foreign,self.foreign_title=self.cr.fetchone()
    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(self.observe(),self.before);self.cr.rollback()
    def enable_export(self):
        user=ENV['res.users'].browse(FIXTURE['users']['alice']['id'])
        user.write({'group_ids':[(4,ENV.ref('base.group_allow_export').id)]})
        self.assertTrue(self.a.user.has_group('base.group_allow_export'))
    def test_id_only_and_empty_web_reads_enforce_workspace(self):
        for spec in [{'id':{}},{}]:
            self.assertEqual(self.own.web_read(spec),[{'id':self.own.id}])
            for ids in [[self.foreign],[self.own.id,self.foreign],[2147483647]]:
                with self.assertRaises(AccessError):self.a['mp.example.note'].browse(ids).web_read(spec)
            unscoped=api.Environment(self.cr,FIXTURE['users']['alice']['id'],{})
            with self.assertRaises(AccessError):unscoped['mp.example.note'].browse(self.own.id).web_read(spec)
    def test_authorized_export_positive_foreign_mixed_and_no_scope(self):
        self.enable_export()
        self.assertEqual(self.own.export_data(['title','body'])['datas'],[[self.own.title,self.own.body]])
        for fields in [['title'],['.id']]:
            for ids in [[self.foreign],[self.own.id,self.foreign],[2147483647]]:
                with self.assertRaises(AccessError):self.a['mp.example.note'].browse(ids).export_data(fields)
        unscoped=api.Environment(self.cr,FIXTURE['users']['alice']['id'],{})
        with self.assertRaises(AccessError):unscoped['mp.example.note'].browse(self.own.id).export_data(['title'])
    def test_native_import_create_and_CAS_update(self):
        title='ID03 import '+uuid4().hex
        result=self.a['mp.example.note'].load(['title','body'],[[title,'Scoped import body']])
        self.assertEqual(len(result['ids']),1);record=self.a['mp.example.note'].browse(result['ids'])
        self.assertEqual(record.workspace_id.id,FIXTURE['workspaces']['A']['id']);self.assertEqual(record.revision,1)
        updated=self.a['mp.example.note'].with_context(expected_revision=1).load(['.id','title'],[[str(record.id),title+' changed']])
        self.assertEqual(updated['ids'],record.ids);self.assertEqual(record.revision,2)
    def test_native_import_foreign_ID_and_ownership_fail(self):
        result=self.a['mp.example.note'].with_context(expected_revision=1).load(['.id','title'],[[str(self.foreign),'Denied foreign import']])
        self.assertFalse(result['ids']);self.assertTrue(any(m['type']=='error' for m in result['messages']))
        self.cr.execute('SELECT title FROM mp_example_note WHERE id=%s',[self.foreign]);self.assertEqual(self.cr.fetchone()[0],self.foreign_title)
        with self.assertRaises(AccessError):self.own.with_context(expected_revision=1).write({'workspace_id':FIXTURE['workspaces']['B']['id']})
    def test_viewer_import_and_mixed_native_save_fail(self):
        result=self.b['mp.example.note'].load(['title'],[['Denied viewer import']]);self.assertFalse(result['ids'])
        with self.assertRaises(AccessError):self.a['mp.example.note'].browse([self.own.id,self.foreign]).web_save({'title':'Denied mixed native save'},specification={'title':{}})
        self.assertEqual(self.own.revision,1)
    def attachment(self,managed=True,public=True):
        payload=('ID03 binary '+uuid4().hex).encode();token=uuid4().hex
        self.cr.execute("""INSERT INTO ir_attachment(name,res_model,res_id,type,public,access_token,db_datas,file_size,checksum,mimetype,create_uid,write_uid,create_date,write_date)
          VALUES('ID03 rollback binary',%s,%s,'binary',%s,%s,%s,%s,%s,'text/plain',1,1,timezone('UTC',now()),timezone('UTC',now())) RETURNING id""",
          ['mp.example.note' if managed else 'ir.ui.view',self.own.id if managed else 0,public,token,payload,len(payload),hashlib.sha1(payload).hexdigest()])
        return self.cr.fetchone()[0],token,payload
    def test_workspace_public_token_and_direct_stream_shortcuts_deny(self):
        public=api.Environment(self.cr,ENV.ref('base.public_user').id,{})
        ident,token,payload=self.attachment()
        for actor in [public,self.a]:
            for credential in [None,token]:
                with self.assertRaises(AccessError):
                    record=actor['ir.binary']._find_record(res_model='ir.attachment',res_id=ident,access_token=credential)
                    actor['ir.binary']._get_stream_from(record,'raw')
            with self.assertRaises(AccessError):actor['ir.attachment'].browse(ident).sudo()._to_http_stream()
    def test_native_limited_field_token_cannot_stream_workspace_attachment(self):
        ident,_,_=self.attachment(public=False);record=ENV['ir.attachment'].browse(ident)
        token=limited_field_access_token(record,'raw',timestamp=str(hex(int(time.time())+120))[2:],scope='binary')
        public=api.Environment(self.cr,ENV.ref('base.public_user').id,{})
        selected=public['ir.binary']._find_record(res_model='ir.attachment',res_id=ident,field='raw',access_token=token)
        with self.assertRaises(AccessError):public['ir.binary']._get_stream_from(selected,'raw')
    def test_unrelated_public_asset_and_token_stream_still_work(self):
        public=api.Environment(self.cr,ENV.ref('base.public_user').id,{})
        ident,token,payload=self.attachment(managed=False)
        for credential in [None,token]:
            record=public['ir.binary']._find_record(res_model='ir.attachment',res_id=ident,access_token=credential)
            stream=public['ir.binary']._get_stream_from(record,'raw');self.assertEqual(stream.data,payload)
