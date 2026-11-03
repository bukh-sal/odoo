"""Installed actor/grant preserving provider chain; all mutations rolled back."""
import json,unittest
from dataclasses import replace
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment,current_scope
from odoo.addons.mp_core.dispatch import CallFrame,authorize_bound,call_bound
class ProviderAuthority(unittest.TestCase):
 def setUp(self):
  env.cr.rollback();env.invalidate_all();self.cr=env.cr
  self.cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels' AND state='installed'")
  self.labels=self.cr.fetchone()[0]
  self.base=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
  self.note=self.base['mp.example.note'].create(dict(title='Rollback-only provider proof',body='Retain actor and body'))
 def tearDown(self):env.cr.rollback();env.invalidate_all()
 def caller(self,workspace='A'):
  native=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
  frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces'][workspace]['public_id'],FIXTURE['site_id'],self.labels,'org.example.notes_labels',())
  return native(context={**native.context,'_mp_call_frame':frame})
 def test_child_retains_actor_workspace_and_scoped_model(self):
  caller=self.caller();bound=authorize_bound(caller,'documents','get');child=bound.model.env.context['_mp_call_frame'];parent=caller.context['_mp_call_frame']
  self.assertEqual((child.principal_id,child.workspace_id,child.site_id),(parent.principal_id,parent.workspace_id,parent.site_id))
  self.assertEqual(bound.model.env.uid,FIXTURE['users']['alice']['id']);self.assertFalse(bound.model.env.su)
  self.assertEqual(current_scope(bound.model.env).principal_public_id,parent.principal_id)
  self.assertEqual(child.provider_plugin_id,'org.example.notes');self.assertEqual(len(child.chain),1)
  self.assertEqual(bound.invoke(dict(note_id=self.note.public_id))['id'],self.note.public_id)
 def test_supported_labels_write_keeps_original_actor(self):
  caller=self.caller();result=caller['mp.example.note']._mp_service_set_labels(dict(note_id=self.note.public_id,expected_revision=1,labels=['reference']))
  self.assertEqual(result['revision'],2);self.assertEqual(result['labels'],['reference']);self.assertEqual(result['body'],'Retain actor and body')
  self.cr.execute('SELECT write_uid FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone()[0],FIXTURE['users']['alice']['id'])
 def test_revoked_integration_grant_denies_nested_read_and_write(self):
  caller=self.caller();call_bound(caller,'documents','get',dict(note_id=self.note.public_id))
  self.cr.execute("UPDATE mp_plugin_grant SET state='revoked' WHERE installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s) AND workspace_id=%s AND capability='org.example.notes:notes.read' AND state='approved'",[self.labels,FIXTURE['workspaces']['A']['id']]);self.assertEqual(self.cr.rowcount,1)
  with self.assertRaises(AccessError):call_bound(caller,'documents','get',dict(note_id=self.note.public_id))
  with self.assertRaises(AccessError):caller['mp.example.note']._mp_service_set_labels(dict(note_id=self.note.public_id,expected_revision=1,labels=['Denied']))
  self.note.invalidate_recordset();self.assertEqual(self.note.revision,1)
 def test_viewer_cannot_gain_write_through_labels_provider(self):
  viewer=self.caller('B');self.cr.execute('SELECT public_id,revision FROM mp_example_note WHERE workspace_id=%s',[FIXTURE['workspaces']['B']['id']]);ident,revision=self.cr.fetchone()
  with self.assertRaises(AccessError):viewer['mp.example.note']._mp_service_set_labels(dict(note_id=ident,expected_revision=revision,labels=['Denied']))
  self.cr.execute('SELECT revision FROM mp_example_note WHERE public_id=%s',[ident]);self.assertEqual(self.cr.fetchone()[0],revision)
 def test_private_frame_mismatch_and_metadata_spoofing_rejected(self):
  caller=self.caller();frame=caller.context['_mp_call_frame']
  variants=[{'principal_id':frame.principal_id},replace(frame,principal_id=FIXTURE['users']['bob']['principal_id']),replace(frame,workspace_id=FIXTURE['workspaces']['B']['public_id']),replace(frame,provider_plugin_id='org.modularplatform.core'),replace(frame,site_id=str(uuid4()))]
  for forged in variants:
   with self.subTest(frame_type=type(forged).__name__):
    with self.assertRaises(AccessError):authorize_bound(caller(context={**caller.context,'_mp_call_frame':forged}),'documents','get')
