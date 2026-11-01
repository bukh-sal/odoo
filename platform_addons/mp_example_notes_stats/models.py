"""Optional analysis actions; no new fields, records, or CRUD screens."""
from uuid import uuid4
from odoo import api, models
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import current_scope
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core.dispatch import call_bound
from odoo.addons.mp_core import job_dispatch

IDENT='org.example.notes_stats:analyze'


def guard(model):
    # The abstract service has no records to expose. Both its own feature and
    # Notes must remain available, including before cached gateway responses.
    model.env['mp.plugin.installation'].flush_model(['state'])
    model.env['mp.workspace.plugin'].flush_model(['availability'])
    model.env['mp.plugin.grant'].flush_model(['state'])
    model.env['mp.service.binding'].flush_model(['state'])
    scope=model.env['mp.example.note']._mp_guard('read')
    model.env.cr.execute("""SELECT 1 FROM mp_workspace_plugin f JOIN mp_plugin_installation i ON i.id=f.installation_id
        WHERE f.workspace_id=%s AND i.plugin_id='org.example.notes_stats' AND i.state='installed'
          AND f.availability='enabled' FOR SHARE OF f,i""",[scope.workspace_id])
    if not model.env.cr.fetchone():raise PublicError('PLUGIN_SUSPENDED')
    return current_scope(model.env)


class NotesStats(models.AbstractModel):
    _name='mp.example.notes.stats'
    _description='Optional Note analysis service'

    @api.model
    def _mp_guard(self,operation):
        if operation!='read':raise AccessError('Read-only analysis service')
        return guard(self)

    @api.model
    def _mp_service_analyze(self,values):
        guard(self)
        # Authorize the job against the read-only status method. Re-entering
        # analyze would correctly trip the provider-chain cycle detector.
        ident=job_dispatch.enqueue_bound(self.env,'jobs',IDENT,values,uuid4().hex)
        return dict(job=job_dispatch.status(self.env,ident))

    @api.model
    def _mp_service_analysis_status(self,values):
        scope=guard(self)
        call_bound(self.env,'documents','get',values)
        frame=self.env.context['_mp_call_frame']
        self.env.cr.execute("""SELECT j.public_id FROM mp_job j JOIN mp_plugin_installation i ON i.id=j.installation_id
            WHERE j.actor_id=%s AND j.workspace_id=%s AND j.handler=%s AND j.handler_version=1
              AND i.public_id=%s AND j.payload->'input'->>'note_id'=%s
            ORDER BY j.created_at DESC,j.id DESC LIMIT 1""",
            [scope.principal_id,scope.workspace_id,IDENT,frame.provider_installation_id,values['note_id']])
        row=self.env.cr.fetchone()
        return dict(job=job_dispatch.status(self.env,row[0]) if row else None)
