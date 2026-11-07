from datetime import timedelta, timezone
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.mp_core import job_dispatch
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_identity.release import current_release
from modular_platform.durable import JobSchedule


PLUGIN = 'org.example.background'
SERVICE = PLUGIN + '.jobs'


class Task(models.Model):
    _name = 'mp.background.task'
    _description = 'Reference scheduled task'
    _inherit = ['mp.workspace.scoped']
    _mp_plugin_id = PLUGIN

    public_id = fields.Char(default=lambda self: str(uuid4()), required=True, readonly=True, index=True)
    name = fields.Char(required=True, size=200)
    due_at = fields.Datetime()
    assignee_id = fields.Many2one('mp.principal', ondelete='restrict')
    done = fields.Boolean()
    revision = fields.Integer(required=True, default=1, readonly=True)
    points = fields.Integer()
    _identity_unique = models.Constraint('UNIQUE(public_id)', 'Unique task identity required')
    _points_range = models.Constraint('CHECK(points BETWEEN 0 AND 1000)', 'Points must be between 0 and 1000')

    @api.constrains('assignee_id', 'workspace_id')
    def _validate_assignee(self):
        for row in self:
            if row.assignee_id and not row._active_recipient():
                raise ValidationError('Assign an active workspace member.')

    def _active_recipient(self, *, lock=False):
        self.ensure_one()
        self.env.cr.execute("""SELECT 1 FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id
            JOIN res_users u ON u.id=p.user_id WHERE m.workspace_id=%s AND p.id=%s
            AND p.kind='human' AND p.state='active' AND m.state='active' AND u.active"""
            + (' FOR SHARE OF m,p,u' if lock else ''), [self.workspace_id.id, self.assignee_id.id or 0])
        return bool(self.env.cr.fetchone())

    @api.model_create_multi
    def create(self, values_list):
        if any(set(values)-{'name','due_at','assignee_id','done','points','workspace_id'} for values in values_list):
            raise AccessError('Only declared task input fields can be created.')
        rows = super().create(values_list)
        for row in rows:
            row._queue_current()
        return rows

    def write(self, values):
        if set(values)-{'name','due_at','assignee_id','done','points'}:
            raise AccessError('Only declared task input fields can be changed.')
        if not self or not set(values) & {'due_at','assignee_id','done'}:
            return super().write(values)
        self._mp_guard('write')
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM mp_background_task WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [self.ids])
        self.invalidate_recordset(['revision'])
        for row in self:
            super(Task,row).write({**values, 'revision': row.revision+1})
            row._queue_current()
        return True

    def _job_env(self):
        scope = self._mp_guard('read')
        release = current_release(self.env)
        self.env.cr.execute("""SELECT i.public_id FROM mp_plugin_installation i
            JOIN mp_workspace_plugin w ON w.installation_id=i.id
            WHERE i.plugin_id=%s AND i.state='installed' AND w.workspace_id=%s AND w.availability='enabled'""",
            [PLUGIN, scope.workspace_id])
        installation = self.env.cr.fetchone()
        if not installation:
            raise AccessError('Reference plugin unavailable.')
        frame = CallFrame(scope.principal_public_id, scope.workspace_public_id, release['site_id'],
                          installation[0], PLUGIN, ())
        return self.with_context(_mp_call_frame=frame).env

    def _queue_current(self):
        self.ensure_one()
        if self.done or not self.assignee_id or not self.due_at:
            return None
        run_at = self.due_at.replace(tzinfo=timezone.utc)
        expires = run_at + timedelta(seconds=60)
        now = fields.Datetime.now().replace(tzinfo=timezone.utc)
        if not now < expires or run_at > now + timedelta(days=30):
            return None
        return job_dispatch.enqueue_scheduled(self._job_env(), 'jobs', PLUGIN+':remind',
            dict(task=self.public_id, revision=self.revision), f'{self.public_id}:{self.revision}',
            schedule=JobSchedule(run_at, expires, 5))

    @api.model
    def _task_by_public(self, ident):
        self._mp_guard('read')
        task = self.search([('public_id','=',ident)], limit=1)
        if not task:
            raise MissingError('Task unavailable.')
        return task

    @api.model
    def _mp_service_job_authority(self, _):
        return {}


class Notification(models.Model):
    _name = 'mp.background.notification'
    _description = 'Private reference reminder effect'

    task_id = fields.Many2one('mp.background.task', required=True, ondelete='restrict')
    recipient_id = fields.Many2one('mp.principal', required=True, ondelete='restrict')
    revision = fields.Integer(required=True)
    _one_per_occurrence = models.Constraint('UNIQUE(task_id, revision)', 'One notification per occurrence')
