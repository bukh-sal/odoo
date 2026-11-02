"""Minimal actual empty-board storage, contract, CAS and scope cases."""
import unittest
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError,MissingError,ValidationError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame,call_bound
from odoo.addons.mp_core.controllers import PublicError
from modular_platform.contracts import ContractError

class EmptyBoardTests(unittest.TestCase):
 def actor(self,user,workspace):
  native=scoped_environment(api.Environment(self.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id']);scope=native.context['_mp_scope']
  self.cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.canvas' AND state='installed'");installation=self.cr.fetchone()[0]
  return native(context={**native.context,'_mp_call_frame':CallFrame(scope.principal_public_id,scope.workspace_public_id,FIXTURE['site_id'],installation,'org.example.canvas',())})
 def rows(self):
  self.cr.execute('SELECT to_jsonb(t) FROM mp_example_canvas_board t ORDER BY id');return self.cr.fetchall()
 def setUp(self):
  ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr;self.before=self.rows()
  self.a=self.actor('alice','A');self.b=self.actor('bob','B');self.viewer=self.actor('alice','B')
  self.board=self.a['mp.example.canvas.board'].search([],limit=1);self.assertTrue(self.board);self.original=self.board._dto()
 def tearDown(self):
  self.cr.rollback();ENV.invalidate_all();self.assertEqual(self.rows(),self.before);self.cr.rollback()
 def card(self,note=None):return dict(id=str(uuid4()),text='Minimal storage test',lane='inbox',note_id=note)
 def save(self,values=None,native=None,**changes):
  data=dict(board_id=self.original['id'],expected_revision=self.original['revision'],name=self.original['name'],cards=[])
  data.update(values or {});data.update(changes);return call_bound(native or self.a,'boards','save',data)
 def assert_empty_database(self,board):
  board.flush_recordset(['cards']);self.cr.execute('SELECT cards IS NULL FROM mp_example_canvas_board WHERE id=%s',[board.id]);self.assertEqual(self.cr.fetchone(),(True,))
  board.invalidate_recordset(['cards']);self.assertEqual(board._dto()['cards'],[])
 def test_native_schema_drops_only_empty_json_notnull(self):
  self.cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid='mp_example_canvas_board'::regclass AND attname='cards'");self.assertEqual(self.cr.fetchone(),(False,))
  self.assertFalse(self.a['mp.example.canvas.board']._fields['cards'].required)
 def test_default_empty_create_and_native_reload(self):
  board=self.b['mp.example.canvas.board'].create(dict(name='Default empty reference'))
  self.assert_empty_database(board);self.assertEqual(board.revision,1)
 def test_explicit_empty_create_and_bound_get(self):
  board=self.b['mp.example.canvas.board'].create(dict(name='Explicit empty reference',cards=[]))
  self.assert_empty_database(board);result=call_bound(self.b,'boards','get',dict(board_id=board.public_id));self.assertEqual(result['cards'],[])
 def test_bound_clear_last_card_and_empty_nonempty_round_trip(self):
  self.assertTrue(self.original['cards'])
  empty=self.save();self.assertEqual(empty['cards'],[]);self.assertEqual(empty['revision'],self.original['revision']+1);self.assert_empty_database(self.board)
  self.assertEqual(call_bound(self.a,'boards','get',{'board_id':empty['id']}),empty)
  card=self.card();full=self.save(expected_revision=empty['revision'],cards=[card]);self.assertEqual(full['cards'],[card])
  final=self.save(expected_revision=full['revision']);self.assertEqual(final['cards'],[]);self.assert_empty_database(self.board)
 def test_invalid_public_json_and_boolean_revision_rejected_before_write(self):
  for invalid in [None,False,{},'']:
   with self.assertRaises(ContractError):self.save(cards=invalid)
  with self.assertRaises(ContractError):self.save(expected_revision=True)
  self.assertEqual(self.board._dto(),self.original)
 def test_stale_CAS_after_empty_save_does_not_overwrite(self):
  empty=self.save()
  with self.assertRaises(PublicError) as error:self.save(cards=[self.card()])
  self.assertEqual(error.exception.code,'CONFLICT');self.assertEqual(self.board._dto(),empty)
 def test_viewer_foreign_missing_and_empty_web_read_scope(self):
  own=self.b['mp.example.canvas.board'].create(dict(name='Viewer empty fixture'))
  self.assertEqual(call_bound(self.viewer,'boards','get',{'board_id':own.public_id})['cards'],[])
  with self.assertRaises(AccessError):self.save(native=self.viewer,board_id=own.public_id,expected_revision=1)
  for ident in [self.original['id'],str(uuid4())]:
   with self.assertRaises(MissingError):call_bound(self.b,'boards','get',{'board_id':ident})
  with self.assertRaises(AccessError):self.b['mp.example.canvas.board'].browse(self.board.id).web_read({})
 def test_nonempty_note_reference_validation_preserved(self):
  self.cr.execute('SELECT public_id FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces']['A']['id']]);own=self.cr.fetchone()[0]
  self.cr.execute('SELECT public_id FROM mp_example_note WHERE workspace_id=%s ORDER BY id LIMIT 1',[FIXTURE['workspaces']['B']['id']]);foreign=self.cr.fetchone()[0]
  result=self.save(cards=[self.card(own)])
  for ident in [foreign,str(uuid4())]:
   with self.assertRaises(MissingError):
    with self.cr.savepoint():self.save(expected_revision=result['revision'],cards=[self.card(ident)])
   self.assertEqual(self.board._dto(),result)
  with self.assertRaises(ValidationError):
   with self.cr.savepoint():self.board.with_context(expected_revision=result['revision']).write({'cards':[{'invalid':'card'}]})
  self.assertEqual(self.board._dto(),result)
 def test_standard_Notes_views_remain_native(self):
  for user,workspace in [('alice','A'),('alice','B'),('alice','C')]:
   native=scoped_environment(api.Environment(self.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
   for kind in ['list','form']:self.assertIn('<'+kind,native['mp.example.note'].get_view(view_type=kind)['arch'])
