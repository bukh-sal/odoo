"""Actual finite-read authorization/isolation/invalidation regression cases."""
import concurrent.futures,time,unittest
from dataclasses import replace
from odoo import api,sql_db
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_identity.read_window import KEY

class ReadWindowTests(unittest.TestCase):
 def actor(self,user='alice',workspace='A'):
  return scoped_environment(api.Environment(self.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
 def setUp(self):
  ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr;self.a=self.actor();self.b=self.actor('bob','B')
  self.notes=self.a['mp.example.note'].search([],order='id',limit=2);self.assertEqual(len(self.notes),2)
  self.note=self.notes[0];self.body=self.note.body;self.other=self.b['mp.example.note'].search([],limit=1);self.other.body
  self.scope=self.a.context['_mp_scope']
 def tearDown(self):self.cr.rollback();ENV.invalidate_all()
 def test_clean_warmed_fields_reuse_only_explicit_bounded_recordset(self):
  # A second row's Char field may need a native lazy fetch even though the
  # first row's Text field was warmed. Measure that separately, then test
  # genuinely warmed values; data fetching/entry guards are not cache reuse.
  with self.notes._mp_read_window() as records:
   count=self.cr.sql_log_count;self.assertEqual(records[0].body,self.body);body_queries=self.cr.sql_log_count-count
   count=self.cr.sql_log_count;records[1].title;title_queries=self.cr.sql_log_count-count
  import json
  print('MP_READ_WARM_DIAG='+json.dumps(dict(first_body_queries=body_queries,first_second_row_title_queries=title_queries)))
  with self.notes._mp_read_window() as records:
   count=self.cr.sql_log_count;self.assertEqual(records[0].body,self.body);records[1].title
   self.assertEqual(self.cr.sql_log_count,count)
   count=self.cr.sql_log_count;self.note.body;self.assertGreaterEqual(self.cr.sql_log_count-count,4)
 def test_missing_and_mixed_foreign_records_fail_before_serialization(self):
  for ids in [[2147483647],[self.note.id,self.other.id]]:
   with self.assertRaises(AccessError):
    with self.a['mp.example.note'].browse(ids)._mp_read_window():pass
 def test_foreign_ID_and_virtual_origin_cannot_borrow_window(self):
  with self.note._mp_read_window() as record:
   foreign=self.a['mp.example.note'].browse(self.other.id).with_context(**{KEY:record.env.context[KEY]})
   for target in [foreign,foreign.new({'body':'Local value'},origin=foreign)]:
    with self.assertRaises(AccessError):target.body
 def test_user_workspace_and_narrowed_action_cannot_borrow_window(self):
  with self.note._mp_read_window() as record:
   window=record.env.context[KEY]
   viewer=self.actor(workspace='B');wrong_workspace=record.with_env(viewer(context={**viewer.context,KEY:window}))
   narrowed=replace(self.scope,allowed_actions=frozenset({'write'}))
   for target in [record.with_user(FIXTURE['users']['bob']['id']),wrong_workspace,record.with_context(_mp_scope=narrowed)]:
    with self.assertRaises(AccessError):target.body
 def test_changed_native_context_does_not_borrow_authorization(self):
  with self.note._mp_read_window() as record:
   changed=record.with_context(read_context_extension='different')
   self.assertIsNone(record.env.context[KEY].scope_for(changed))
   count=self.cr.sql_log_count;self.assertEqual(changed.body,self.body)
   self.assertGreaterEqual(self.cr.sql_log_count-count,4)
 def test_different_model_uses_its_full_guard(self):
  with self.note._mp_read_window() as record:
   board=record.env['mp.example.canvas.board'].search([],limit=1);self.assertTrue(board)
   count=self.cr.sql_log_count;board.name;self.assertGreaterEqual(self.cr.sql_log_count-count,4)
 def test_no_cross_cursor_or_thread_reuse(self):
  with self.note._mp_read_window() as record:
   window=record.env.context[KEY]
   with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:self.assertIsNone(pool.submit(window.scope_for,record).result())
   with sql_db.db_connect(self.cr.dbname).cursor() as other:
    foreign=api.Environment(other,self.a.uid,dict(record.env.context))['mp.example.note'].browse(self.note.id)
    self.assertIsNone(window.scope_for(foreign))
 def test_ORM_membership_revoke_inside_window_denies_cached_field(self):
  with self.note._mp_read_window() as record:
   record.body
   membership=ENV['mp.membership'].search([('principal_id','=',self.scope.principal_id),('workspace_id','=',self.scope.workspace_id)])
   membership.write({'state':'revoked'})
   with self.assertRaises(AccessError):record.body
 def test_pending_feature_and_installation_state_inside_window_denied(self):
  for kind in ['feature','installation']:
   try:
    with self.cr.savepoint():
     with self.note._mp_read_window() as record:
      if kind=='feature':ENV['mp.workspace.plugin'].search([('workspace_id','=',self.scope.workspace_id),('plugin_id','=','org.example.notes')]).write({'availability':'suspended'})
      else:ENV['mp.plugin.installation'].search([('plugin_id','=','org.example.notes')]).write({'state':'suspended'})
      with self.assertRaises(AccessError):record.body
     # Deliberately roll back the variant, not a field/cache workaround.
     raise RollbackVariant()
   except RollbackVariant:pass
 def test_raw_SQL_revoke_invalidates_before_cached_field(self):
  with self.note._mp_read_window() as record:
   self.cr.execute("UPDATE mp_membership SET state='revoked' WHERE principal_id=%s AND workspace_id=%s",[self.scope.principal_id,self.scope.workspace_id])
   with self.assertRaises(AccessError):record.body
 def test_multi_statement_SQL_revoke_invalidates(self):
  with self.note._mp_read_window() as record:
   self.cr.execute("SELECT 1; UPDATE mp_membership SET state='revoked' WHERE principal_id=%s AND workspace_id=%s",[self.scope.principal_id,self.scope.workspace_id])
   with self.assertRaises(AccessError):record.body
 def test_raw_SQL_ownership_change_cannot_serve_old_cached_body(self):
  with self.note._mp_read_window() as record:
   self.cr.execute('UPDATE mp_example_note SET workspace_id=%s WHERE id=%s',[FIXTURE['workspaces']['B']['id'],self.note.id])
   with self.assertRaises(AccessError):record.body
 def test_closed_window_and_forged_dictionary_do_not_authorize(self):
  with self.note._mp_read_window() as record:record.body
  self.cr.execute("UPDATE mp_membership SET state='revoked' WHERE principal_id=%s AND workspace_id=%s",[self.scope.principal_id,self.scope.workspace_id])
  for target in [record,self.note.with_context(**{KEY:dict(active=True,scope='administrator')})]:
   with self.assertRaises(AccessError):target.body
 def test_short_expiry_rechecks_authoritative_SQL(self):
  with self.note._mp_read_window() as record:
   record.body;count=self.cr.sql_log_count;time.sleep(.035);record.body
   self.assertGreaterEqual(self.cr.sql_log_count-count,4)
 def test_viewer_write_stays_denied_and_hook_closes_on_error(self):
  import threading
  viewer=self.actor(workspace='B');note=viewer['mp.example.note'].browse(self.other.id)
  hooks=list(getattr(threading.current_thread(),'query_hooks',[]))
  with self.assertRaises(AccessError):
   with note._mp_read_window() as record:record.with_context(expected_revision=1).write({'body':'Forbidden'})
  self.assertEqual(list(getattr(threading.current_thread(),'query_hooks',[])),hooks)

class RollbackVariant(Exception):pass
