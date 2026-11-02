"""Actual native cached-field and virtual-origin scope regressions."""
import unittest
from dataclasses import replace
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment

class NativeCacheTests(unittest.TestCase):
    def actor(self,user='alice',workspace='A'):
        return scoped_environment(api.Environment(self.cr,FIXTURE['users'][user]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr
        self.a=self.actor()
        self.note=self.a['mp.example.note'].search([],order='id',limit=1)
        self.assertTrue(self.note)
        self.body=self.note.body
        self.assertEqual(self.note.body,self.body)
    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all()
    def denied(self,record):
        for operation in [lambda:record.body,lambda:record['body'],lambda:record.mapped('body'),lambda:record.workspace_id]:
            with self.assertRaises(AccessError):operation()
    def test_distinct_workspace_environment_denies_warmed_fields(self):
        self.denied(self.actor(workspace='B')['mp.example.note'].browse(self.note.id))
        self.assertEqual(self.note.body,self.body)
    def test_distinct_principal_environment_denies_warmed_fields(self):
        self.denied(self.actor('bob','B')['mp.example.note'].browse(self.note.id))
    def test_unscoped_environment_denies_warmed_fields(self):
        self.denied(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{})['mp.example.note'].browse(self.note.id))
    def test_warmed_fields_recheck_pending_membership_revocation(self):
        membership=ENV['mp.membership'].search([('principal_id','=',self.a.context['_mp_scope'].principal_id),('workspace_id','=',FIXTURE['workspaces']['A']['id'])])
        membership.write({'state':'revoked'})
        self.denied(self.note)
    def test_warmed_fields_recheck_pending_feature_suspension(self):
        feature=ENV['mp.workspace.plugin'].search([('workspace_id','=',FIXTURE['workspaces']['A']['id']),('plugin_id','=','org.example.notes')])
        feature.write({'availability':'suspended'})
        self.denied(self.note)
    def test_warmed_fields_recheck_pending_actor_deactivation(self):
        ENV['res.users'].browse(FIXTURE['users']['alice']['id']).write({'active':False})
        self.denied(self.note)
    def test_warmed_fields_recheck_technical_action_restriction(self):
        # A narrowed trusted dispatch context cannot widen back to read merely
        # because a preceding native computation cached this field.
        scope=replace(self.a.context['_mp_scope'],allowed_actions=frozenset({'write'}))
        restricted=self.a(context={**self.a.context,'_mp_scope':scope})
        self.denied(restricted['mp.example.note'].browse(self.note.id))
    def test_foreign_virtual_origin_and_mixed_origin_denied(self):
        b=self.actor(workspace='B')['mp.example.note']
        virtual=b.new({'body':'Local virtual value'},origin=b.browse(self.note.id))
        self.denied(virtual)
        with self.assertRaises(AccessError):virtual.read(['body'])
    def test_own_virtual_origin_new_record_and_metadata_retained(self):
        own=self.a['mp.example.note'].new({'body':'Own onchange value'},origin=self.note)
        self.assertEqual(own.body,'Own onchange value')
        pure=self.a['mp.example.note'].new({'title':'New draft','body':'Draft body'})
        self.assertEqual(pure.body,'Draft body')
        self.assertIn('body',api.Environment(self.cr,FIXTURE['users']['alice']['id'],{})['mp.example.note'].fields_get(['body']))
        self.assertEqual(self.note.mapped('body'),[self.body])
    def test_viewer_own_read_and_write_denial_retained(self):
        editor=self.actor('bob','B')
        record=editor['mp.example.note'].search([],order='id',limit=1)
        expected=record.body
        viewer=self.actor(workspace='B')['mp.example.note'].browse(record.id)
        self.assertEqual(viewer.body,expected)
        with self.assertRaises(AccessError):viewer.with_context(expected_revision=1).write({'body':'Denied'})
