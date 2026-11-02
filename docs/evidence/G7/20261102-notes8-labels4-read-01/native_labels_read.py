"""Actual Labels read-policy and Notes DTO tests, rollback-only existing rows."""
class LabelsReadTests(unittest.TestCase):
 actor=ReadWindowTests.actor
 setUp=ReadWindowTests.setUp
 tearDown=ReadWindowTests.tearDown
 def test_DTO_v1_v2_get_list_and_empty_list(self):
  model=self.a['mp.example.note'];ident=self.note.public_id
  one=model._mp_service_get({'note_id':ident});two=model._mp_service_v2_get({'document_id':ident})
  self.assertEqual(two['document_id'],one['id']);self.assertEqual(two['content'],{'headline':one['title'],'text':one['body']})
  first=model._mp_service_list({'limit':2,'order':'title_asc'})['items'];second=model._mp_service_v2_list({'limit':2})['documents']
  self.assertEqual([v['id'] for v in first],[v['document_id'] for v in second]);self.assertEqual(len(first),2)
  self.assertEqual(model._mp_service_list({'limit':2,'query':'g7-definitely-absent-query-f8b3'})['items'],[])
 def test_bool_policy_reuses_only_active_read_window(self):
  with self.note._mp_read_window() as record:
   self.assertTrue(record._labels_available(read_window=True));count=self.cr.sql_log_count
   self.assertTrue(record._labels_available(read_window=True));self.assertEqual(count,self.cr.sql_log_count)
  count=self.cr.sql_log_count;self.assertTrue(record._labels_available(read_window=True));self.assertGreaterEqual(self.cr.sql_log_count-count,2)
 def pending(self,kind):
  with self.note._mp_read_window() as record:
   record.x_notes_labels;self.assertTrue(record._labels_available(read_window=True))
   if kind=='feature':ENV['mp.workspace.plugin'].search([('workspace_id','=',self.scope.workspace_id),('plugin_id','=','org.example.notes_labels')]).write({'availability':'suspended'})
   else:ENV['mp.plugin.installation'].search([('plugin_id','=','org.example.notes_labels')]).write({'state':'suspended'})
   self.assertFalse(record._labels_available(read_window=True))
   with self.assertRaises(AccessError):record.x_notes_labels
   self.assertEqual(record._dto()['labels'],[])
 def test_pending_ORM_feature_policy_denies(self):self.pending('feature')
 def test_pending_ORM_installation_policy_denies(self):self.pending('installation')
 def test_SQL_invalidation_does_not_retain_true_or_false(self):
  with self.note._mp_read_window() as record:
   record.x_notes_labels;self.assertTrue(record._labels_available(read_window=True))
   self.cr.execute("UPDATE mp_workspace_plugin SET availability='suspended' WHERE workspace_id=%s AND plugin_id='org.example.notes_labels'",[self.scope.workspace_id])
   self.assertFalse(record._labels_available(read_window=True))
   with self.assertRaises(AccessError):record.x_notes_labels
   self.cr.execute("UPDATE mp_workspace_plugin SET availability='enabled' WHERE workspace_id=%s AND plugin_id='org.example.notes_labels'",[self.scope.workspace_id])
   self.assertTrue(record._labels_available(read_window=True));record.x_notes_labels
 def test_write_guard_never_uses_cached_read_availability(self):
  with self.note._mp_read_window() as record:
   self.assertTrue(record._labels_available(read_window=True))
   ENV['mp.plugin.installation'].search([('plugin_id','=','org.example.notes_labels')]).write({'state':'suspended'})
   with self.assertRaises(AccessError):record._labels_guard('write')
 def test_policy_expiry_and_after_exit_stay_fresh(self):
  with self.note._mp_read_window() as record:
   self.assertTrue(record._labels_available(read_window=True));count=self.cr.sql_log_count
   time.sleep(.035);self.assertTrue(record._labels_available(read_window=True));self.assertGreaterEqual(self.cr.sql_log_count-count,5)
  self.cr.execute("UPDATE mp_workspace_plugin SET availability='suspended' WHERE workspace_id=%s AND plugin_id='org.example.notes_labels'",[self.scope.workspace_id])
  self.assertFalse(record._labels_available(read_window=True))
 def test_nonboolean_policy_value_is_rejected(self):
  with self.note._mp_read_window() as record:
   with self.assertRaises(TypeError):record._mp_read_policy('bad-test-policy',lambda:1)

