"""Actual native actor/binding/Note/job checks; all data changes roll back.

Connector's abstract model is loaded only in this isolated process. Compute is NOT
sent to a worker: these checks qualify source prerequisites, not installed SVC.
"""
import copy,unittest
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError,MissingError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import dispatch_lifecycle as LC


class NotesAnalysisTests(unittest.TestCase):
    def setUp(self):
        ENV.cr.rollback();ENV.invalidate_all();self.cr=ENV.cr
        self.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");self.release=self.cr.fetchone()[0]
        self.lifecycle=LC.LifecycleScope(FIXTURE['site_id'],self.release);self.before=LC.observe(self.cr,self.lifecycle)
        self.original={}
        for table in ['mp_plugin_installation','mp_service_binding','mp_plugin_grant','mp_workspace_plugin','mp_membership','mp_example_note']:
            self.cr.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id');self.original[table]=self.cr.fetchall()
        self.workspace=FIXTURE['workspaces']['C']
        self.connector=ENV['mp.plugin.installation'].create(dict(public_id=str(uuid4()),plugin_id='org.example.notes_stats',version='0.1.0',artifact_digest='sha256:'+'c'*64,runtime='native',state='installed',manifest=MANIFEST))
        self.feature=ENV['mp.workspace.plugin'].create(dict(workspace_id=self.workspace['id'],plugin_id=self.connector.plugin_id,installation_id=self.connector.id,availability='enabled'))
        self.grant=ENV['mp.plugin.grant'].create(dict(installation_id=self.connector.id,workspace_id=self.workspace['id'],capability='org.example.notes:notes.read',state='approved'))
        for alias,service,plugin,provider in [('documents','org.example.notes.documents','org.example.notes',FIXTURE['bindings']['C']['provider_installation_id']),('jobs','org.example.notes_stats.jobs','org.example.notes_stats',self.connector.public_id)]:
            binding=copy.deepcopy(FIXTURE['bindings']['C']);binding.update(binding_id=str(uuid4()),alias=alias,service_id=service,consumer_installation_id=self.connector.public_id,provider_plugin_id=plugin,provider_installation_id=provider,api_version='1.0',contract_major=1)
            ENV['mp.service.binding'].create(dict(public_id=binding['binding_id'],workspace_id=self.workspace['id'],consumer_id=self.connector.id,alias=alias,descriptor=binding,state='active'))
        self.native=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),self.workspace['public_id'])
        frame=CallFrame(FIXTURE['users']['alice']['principal_id'],self.workspace['public_id'],FIXTURE['site_id'],self.connector.public_id,'org.example.notes_stats',(('org.example.notes_stats','org.example.notes_stats.jobs','analyze'),))
        self.native=self.native(context={**self.native.context,'_mp_call_frame':frame})
        self.note=self.native['mp.example.note'].create(dict(title='Analysis source prerequisite',body='hello world\nagain'))
        self.model=self.native['mp.example.notes.stats'];self.values=dict(note_id=self.note.public_id,expected_revision=1)

    def tearDown(self):
        self.cr.rollback();ENV.invalidate_all();self.assertEqual(LC.observe(self.cr,self.lifecycle),self.before)
        for table,rows in self.original.items():
            self.cr.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id');self.assertEqual(self.cr.fetchall(),rows)
        self.cr.rollback()

    def start(self):return self.model._mp_service_analyze(self.values)['job']
    def status(self,note_id=None):return self.model._mp_service_analysis_status(dict(note_id=note_id or self.note.public_id))['job']
    def deny(self,fn):
        with self.assertRaises((AccessError,PublicError)):fn()

    def test_revision_snapshot_and_read_only_result_use_existing_job_guards(self):
        job=self.start();self.assertEqual(job['state'],'pending');self.assertEqual(self.status()['id'],job['id'])
        invocation=jobs.prepare_one(ENV,str(uuid4()))
        self.assertEqual(invocation.prepared,dict(input=dict(text='hello world\nagain',**self.values)))
        # Deliberately supply schema-valid statistics; no remote compute claim.
        result=jobs.finish_one(ENV,invocation,dict(characters=17,words=3,lines=2))
        self.assertEqual(result,dict(note_id=self.note.public_id,revision=1,statistics=dict(characters=17,words=3,lines=2)))
        self.assertEqual(self.status()['result'],result)
        self.cr.execute('SELECT revision,body FROM mp_example_note WHERE id=%s',[self.note.id]);self.assertEqual(self.cr.fetchone(),(1,'hello world\nagain'))

    def test_stale_revision_does_not_reserve_a_job(self):
        self.values['expected_revision']=2;self.deny(self.start)
        self.assertEqual(self.status(),None)

    def test_pending_connector_suspension_denies_even_on_notes_model(self):
        self.feature.write({'availability':'suspended'});self.deny(self.start);self.deny(self.status)
        self.deny(lambda:self.model._mp_guard('read'))

    def test_pending_notes_grant_revocation_denies_start_and_existing_status(self):
        self.start();self.grant.write({'state':'revoked'})
        self.deny(self.start);self.deny(self.status)

    def test_note_revision_change_before_finish_refuses_stale_statistics(self):
        self.start();invocation=jobs.prepare_one(ENV,str(uuid4()))
        self.note.with_context(expected_revision=1).write({'body':'changed'})
        result=jobs.finish_one(ENV,invocation,dict(characters=17,words=3,lines=2));self.assertEqual(result['error_code'],'CONFLICT')
        self.assertIsNone(self.status()['result'])

    def test_foreign_and_missing_note_status_are_not_found(self):
        foreign=scoped_environment(api.Environment(self.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])['mp.example.note'].search([],limit=1)
        self.assertTrue(foreign)
        for ident in [foreign.public_id,str(uuid4())]:
            # The native gateway maps MissingError to NOT_FOUND. Test the
            # identical native exception here, before that HTTP mapping.
            with self.assertRaises(MissingError):self.status(ident)

    def test_latest_analysis_and_actor_filter(self):
        first=self.start();second=self.start();self.assertNotEqual(first['id'],second['id']);self.assertEqual(self.status()['id'],second['id'])
        self.cr.execute('UPDATE mp_job SET actor_id=(SELECT id FROM mp_principal WHERE user_id=%s) WHERE public_id=ANY(%s)',[FIXTURE['users']['bob']['id'],[first['id'],second['id']]])
        self.assertIsNone(self.status())
