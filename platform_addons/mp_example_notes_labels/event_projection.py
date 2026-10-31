"""Small native reference consumer: count distinct changes and retain max revision."""
from uuid import uuid4
from odoo import api,fields,models
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import current_scope
from odoo.addons.mp_core.events import Consumer,ConsumerFrame,register_consumer

HANDLER='org.example.notes_labels:revision_projection'


class NoteEventSummary(models.Model):
    _name='mp.example.note.event.summary'
    _description='Reference native Notes event projection'
    _inherit=['mp.workspace.scoped']
    _mp_plugin_id='org.example.notes_labels'
    public_id=fields.Char(default=lambda self:str(uuid4()),required=True,index=True,readonly=True)
    note_id=fields.Char(required=True,index=True,readonly=True)
    installation_id=fields.Many2one('mp.plugin.installation',required=True,ondelete='restrict',readonly=True)
    event_count=fields.Integer(required=True,default=0,readonly=True)
    last_revision=fields.Integer(required=True,default=0,readonly=True)
    _scope_unique=models.Constraint('UNIQUE(workspace_id,installation_id,note_id)','One consumer projection per Note/scope')

    def _mp_guard(self,operation):
        scope=super()._mp_guard(operation)
        # Retained derived IDs/counts still need the consumer's current Notes
        # read binding. Direct native RPC must not bypass a revoked integration.
        self.env.cr.execute("""SELECT b.public_id FROM mp_service_binding b JOIN mp_plugin_installation i ON i.id=b.consumer_id
            WHERE b.workspace_id=%s AND i.plugin_id='org.example.notes_labels' AND b.alias='documents' AND b.state='active'""",[scope.workspace_id])
        binding=self.env.cr.fetchone()
        if not binding:raise AccessError('Current event-source binding required')
        from odoo.addons.mp_core.events import _authorize,_topic
        _authorize(self.env,_topic('org.example.notes.changed'),binding[0])
        return scope

    def _projection_guard(self):
        scope=self._mp_guard('write');frame=self.env.context.get('_mp_event_consumer')
        if not isinstance(frame,ConsumerFrame) or (frame.handler,frame.workspace_id)!=(HANDLER,scope.workspace_id):
            raise AccessError('Registered native consumer frame required')
        self.env['mp.example.note']._labels_guard('write')
        self.env.cr.execute("SELECT id FROM mp_plugin_installation WHERE id=%s AND plugin_id='org.example.notes_labels' AND state='installed'",[frame.installation_id])
        if not self.env.cr.fetchone():raise AccessError('Native consumer installation mismatch')
        return frame

    @api.model_create_multi
    def create(self,values_list):
        frame=self._projection_guard()
        if any(set(value)-{'note_id','installation_id','event_count','last_revision'} or value.get('installation_id')!=frame.installation_id for value in values_list):
            raise AccessError('Invalid native projection input')
        return super().create(values_list)

    def write(self,values):
        self._projection_guard()
        if set(values)-{'event_count','last_revision'}:raise AccessError('Projection ownership immutable')
        return super().write(values)

    def unlink(self):raise AccessError('Projection erasure requires an explicit lifecycle operation')


def authorize(env,bound):
    env['mp.example.note']._labels_guard('write')
    scope=current_scope(env)
    if scope.allowed_actions is not None and not {'read','create','write'}<=scope.allowed_actions:
        raise AccessError('Native projection requires explicit read/create/write scopes')


def apply(env,event,bound):
    frame=env.context['_mp_event_consumer'];model=env['mp.example.note.event.summary']
    existing=model.search([('note_id','=',event['aggregate_id']),('installation_id','=',frame.installation_id)],limit=1)
    if existing:
        env.cr.execute('SELECT id FROM mp_example_note_event_summary WHERE id=%s FOR UPDATE',[existing.id]);existing.invalidate_recordset(['event_count','last_revision'])
        existing.write(dict(event_count=existing.event_count+1,last_revision=max(existing.last_revision,event['payload']['revision'])))
    else:model.create(dict(note_id=event['aggregate_id'],installation_id=frame.installation_id,event_count=1,last_revision=event['payload']['revision']))


register_consumer(Consumer(ident=HANDLER,plugin='org.example.notes_labels',topic='org.example.notes.changed',permission='org.example.notes_labels:labels.write',authorize=authorize,apply=apply))
