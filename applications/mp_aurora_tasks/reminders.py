"""Private occurrence linkage and recipient-only native reminder inbox."""
from odoo import _,api,fields,models
from odoo.exceptions import AccessError,MissingError,UserError


class Reminder(models.Model):
    _name='mp.aurora.reminder'
    _description='Private Aurora reminder occurrence'

    task_id=fields.Many2one('mp.aurora.task',required=True,ondelete='cascade',index=True)
    revision=fields.Integer(required=True)
    job_id=fields.Char(required=True,index=True)
    actor_id=fields.Many2one('res.users',required=True,ondelete='restrict')
    _one_occurrence=models.Constraint('UNIQUE(task_id,revision)','One reminder occurrence per task revision')
    _one_job=models.Constraint('UNIQUE(job_id)','One native job per reminder occurrence')
    _positive=models.Constraint('CHECK(revision>0)','Positive reminder revision required')


class Notification(models.Model):
    _name='mp.aurora.notification'
    _description='Aurora reminder inbox'
    _inherit='mp.aurora.access'
    _order='create_date desc,id desc'
    _rec_name='title'

    task_id=fields.Many2one('mp.aurora.task',ondelete='set null',groups='base.group_system')
    revision=fields.Integer(required=True,readonly=True)
    recipient_id=fields.Many2one('res.users',required=True,ondelete='restrict',readonly=True)
    title=fields.Char(required=True,readonly=True)
    due_date=fields.Datetime(readonly=True)
    is_read=fields.Boolean(default=False)
    _one_effect=models.Constraint('UNIQUE(task_id,revision)','One notification per task occurrence')

    @api.model_create_multi
    def create(self,values):raise AccessError(_('Reminders are created by authorized background jobs.'))

    def write(self,values):
        if set(values)-{'is_read'} or 'is_read' in values and type(values['is_read']) is not bool:
            raise AccessError(_('Only the reminder read state can be changed.'))
        return super().write(values)

    def unlink(self):raise AccessError(_('Reminder history cannot be deleted here.'))

    def action_open_task(self):
        self.ensure_one();self.check_access('read')
        self.env.cr.execute('SELECT task_id FROM mp_aurora_notification WHERE id=%s AND recipient_id=%s',[self.id,self.env.uid])
        row=self.env.cr.fetchone()
        if not row or not row[0]:raise UserError(_('This task is no longer available.'))
        task=self.env['mp.aurora.task'].with_context(active_test=False).browse(row[0]).exists()
        if not task:raise UserError(_('This task is no longer available.'))
        task.check_access('read')
        return dict(type='ir.actions.act_window',name=_('Task'),res_model='mp.aurora.task',res_id=task.id,
                    views=[(False,'form')],target='current')
