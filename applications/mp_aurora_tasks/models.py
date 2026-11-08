from datetime import timedelta,timezone

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.mp_core import native_jobs
from modular_platform.durable import JobSchedule

from .access import PLUGIN

HANDLER=PLUGIN+':reminder'
REMINDERS=[('none','No reminder'),('0','At due time'),('15','15 minutes before'),
           ('60','1 hour before'),('1440','1 day before')]
REMINDER_FIELDS={'due_date','reminder','assignee_id','active','stage_id'}
PROTECTED={'reminder_revision','reminder_status','reminder_at','completed'}


class AuroraTaskList(models.Model):
    _name = "mp.aurora.task.list"
    _description = "Aurora task list"
    _inherit='mp.aurora.access'

    name = fields.Char(required=True)
    description = fields.Text()
    owner_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    member_ids = fields.Many2many("res.users", string="Members", domain=[("share", "=", False)])
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, values_list):
        rows=super().create([{**values, "owner_id": self.env.uid} for values in values_list])
        self.env['mp.aurora.task.stage'].create([dict(name=name,list_id=row.id,sequence=sequence,done=done)
            for row in rows for name,sequence,done in [('To do',10,False),('Done',20,True)]])
        return rows

    def write(self, values):
        self.check_access('write')
        if "owner_id" in values:
            raise AccessError(_("The owner is set when the list is created."))
        if {"active", "member_ids"} & values.keys() and any(
            record.owner_id != self.env.user for record in self
        ):
            raise AccessError(_("Only the list owner can manage membership or archive the list."))
        changed=self.filtered(lambda row:row.active!=bool(values['active'])) if 'active' in values else self.browse()
        tasks=self.env['mp.aurora.task'].with_context(active_test=False).search([('list_id','in',changed.ids)]) if changed else self.env['mp.aurora.task']
        if tasks:tasks._cancel_and_lock()
        # This row also fences membership changes against job authorization.
        self.env.cr.execute('SELECT id FROM mp_aurora_task_list WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids])
        result=super().write(values)
        if tasks:tasks._advance_reminders(strict=False)
        return result

    def unlink(self):
        self.check_access('unlink')
        self.env['mp.aurora.task'].with_context(active_test=False).search([('list_id','in',self.ids)])._cancel_and_lock()
        return super().unlink()

    @api.constrains("member_ids")
    def _check_internal_members(self):
        if any(member.share or not member.active for member in self.member_ids):
            raise ValidationError(_("List members must be active internal users."))


class AuroraTaskStage(models.Model):
    _name = "mp.aurora.task.stage"
    _description = "Aurora task stage"
    _inherit='mp.aurora.access'
    _order = "sequence, id"

    name = fields.Char(required=True)
    list_id = fields.Many2one("mp.aurora.task.list", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    done = fields.Boolean()

    def write(self, values):
        self.check_access('write')
        if "list_id" in values and any(stage.list_id.id != values["list_id"] for stage in self):
            raise ValidationError(_("Create a stage in the destination list."))
        if 'done' in values:
            self.env.cr.execute('SELECT id FROM mp_aurora_task_stage WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids])
            self.invalidate_recordset(['done'])
            changed=self.filtered(lambda row:row.done!=bool(values['done']))
            self.env.cr.execute('SELECT 1 FROM mp_aurora_task WHERE stage_id=ANY(%s) LIMIT 1',[changed.ids])
            if self.env.cr.fetchone():raise ValidationError(_('Create a different stage to change completion for existing tasks.'))
        return super().write(values)

    def unlink(self):
        self.check_access('unlink')
        self.env.cr.execute('SELECT id FROM mp_aurora_task_stage WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids])
        self.env.cr.execute('SELECT 1 FROM mp_aurora_task WHERE stage_id=ANY(%s) LIMIT 1',[self.ids])
        if self.env.cr.fetchone():raise ValidationError(_('Move tasks to another stage before deleting this stage.'))
        return super().unlink()


class AuroraTask(models.Model):
    _name = "mp.aurora.task"
    _description = "Aurora task"
    _inherit='mp.aurora.access'

    name = fields.Char(required=True)
    description = fields.Text()
    list_id = fields.Many2one("mp.aurora.task.list", required=True, ondelete="cascade", index=True)
    stage_id = fields.Many2one("mp.aurora.task.stage", ondelete="set null",
                               domain="[('list_id', '=', list_id)]")
    creator_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    assignee_id = fields.Many2one("res.users", ondelete="set null", domain=[("share", "=", False)])
    due_date = fields.Datetime()
    active = fields.Boolean(default=True)
    reminder=fields.Selection(REMINDERS,required=True,default='none')
    reminder_revision=fields.Integer(default=1,required=True,readonly=True)
    reminder_at=fields.Datetime(compute='_compute_reminder_at')
    completed=fields.Boolean(compute='_compute_completed')
    reminder_status=fields.Selection([(s,s.title()) for s in ('disabled','queued','sent','cancelled','expired','blocked')],compute='_compute_reminder_status')
    _revision_positive=models.Constraint('CHECK(reminder_revision>0)','Positive reminder revision required')

    @api.model_create_multi
    def create(self, values_list):
        prepared=[]
        for values in values_list:
            if PROTECTED & values.keys():raise AccessError(_('Reminder state is maintained by the application.'))
            values=dict(values)
            if values.get('list_id'):
                self.env['mp.aurora.task.list'].browse(values['list_id']).check_access('read')
                if not values.get('stage_id'):
                    self.env.cr.execute('SELECT id FROM mp_aurora_task_stage WHERE list_id=%s AND NOT done ORDER BY sequence,id LIMIT 1',[values['list_id']])
                    stage=self.env.cr.fetchone();values['stage_id']=stage[0] if stage else False
            prepared.append({**values,'creator_id':self.env.uid,'active':True})
        rows=super().create(prepared)
        for row in rows:row._queue_current(strict=True)
        return rows

    def write(self, values):
        self.check_access('write')
        if PROTECTED & values.keys():raise AccessError(_('Reminder state is maintained by the application.'))
        if "creator_id" in values:
            raise AccessError(_("The creator is set when the task is created."))
        if "list_id" in values and any(task.list_id.id != values["list_id"] for task in self):
            raise ValidationError(_("Create a task in the destination list."))
        if "active" in values and "assignee_id" in values:
            raise ValidationError(_("Change the assignment and archive state separately."))
        if "active" in values and any(
            (task.assignee_id or task.creator_id) != self.env.user for task in self
        ):
            raise AccessError(_("Only the assignee, or the creator of an unassigned task, can archive it."))
        if not self or not REMINDER_FIELDS & values.keys():return super().write(values)
        changed=self.filtered(lambda row:row._reminder_changed(values))
        if changed:changed._cancel_and_lock()
        for row in self:
            actual=dict(values)
            if row in changed:
                if row.reminder_revision>=2147483647:raise ValidationError(_('Reminder revision limit reached.'))
                actual['reminder_revision']=row.reminder_revision+1
            super(AuroraTask,row).write(actual)
            # Reassignment/unassignment may legitimately remove this editor's
            # task authority. Preserve that write and cancellation; never queue
            # through another user's identity to recover the lost authority.
            if row in changed and row.has_access('write'):
                row._queue_current(strict=bool(values.get('reminder','none')!='none' or values.get('due_date')))
        return True

    def unlink(self):
        self.check_access('unlink');self._cancel_and_lock()
        return super().unlink()

    def _reminder_changed(self,values):
        self.ensure_one()
        for name in REMINDER_FIELDS & values.keys():
            current=self[name]
            if name.endswith('_id'):current=current.id or False;proposed=values[name] or False
            elif name=='due_date':current=current or None;proposed=fields.Datetime.to_datetime(values[name]) or None
            elif name=='active':proposed=bool(values[name])
            else:proposed=values[name]
            if current!=proposed:return True
        return False

    def _cancel_and_lock(self):
        if not self:return
        self.check_access('write')
        self.flush_recordset()
        # Job rows precede task rows in the worker fence too. Repeatable-read
        # retries reject a concurrent editor that replaced the occurrence.
        self.env.cr.execute("""SELECT o.job_id FROM mp_aurora_reminder o JOIN mp_job j ON j.public_id=o.job_id
            WHERE o.task_id=ANY(%s) AND j.state IN ('pending','retry','running','held') ORDER BY o.job_id""",[self.ids])
        for ident, in self.env.cr.fetchall():native_jobs.cancel(self.env,ident)
        self.env.cr.execute('SELECT id FROM mp_aurora_task WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids])
        self.invalidate_recordset(list(REMINDER_FIELDS)+['reminder_revision'])

    def _advance_reminders(self,*,strict):
        for row in self:
            if row.reminder_revision>=2147483647:raise ValidationError(_('Reminder revision limit reached.'))
            super(AuroraTask,row).write({'reminder_revision':row.reminder_revision+1})
            row._queue_current(strict=strict)

    def _facts(self):
        self.ensure_one();self.flush_recordset()
        self.env.cr.execute("""SELECT t.reminder_revision,t.reminder,t.due_date,t.assignee_id,t.active,l.active,
            COALESCE(s.done,false),u.active,COALESCE(u.share,true)
            FROM mp_aurora_task t JOIN mp_aurora_task_list l ON l.id=t.list_id
            LEFT JOIN mp_aurora_task_stage s ON s.id=t.stage_id LEFT JOIN res_users u ON u.id=t.assignee_id
            WHERE t.id=%s""",[self.id])
        return self.env.cr.fetchone()

    def _queue_current(self,*,strict):
        self.ensure_one()
        revision,option,due,recipient,active,list_active,done,user_active,share=self._facts()
        if option=='none':return
        if not due or not recipient or not user_active or share:
            if strict:raise ValidationError(_('Choose a due time and active internal assignee for the reminder.'))
            return
        run_at=(due-timedelta(minutes=int(option))).replace(tzinfo=timezone.utc)
        now=fields.Datetime.now().replace(tzinfo=timezone.utc)
        if run_at>now+timedelta(days=30) or run_at+timedelta(days=1)<=now:
            if strict:raise ValidationError(_('Choose a reminder within the next 30 days and no more than 24 hours overdue.'))
            return
        if not active or not list_active or done:return
        ident=native_jobs.enqueue_scheduled(self.env,HANDLER,dict(task=self.id,revision=revision),
            f'{self.id}:{revision}',schedule=JobSchedule(run_at,run_at+timedelta(days=1),30))
        self.env.cr.execute("""INSERT INTO mp_aurora_reminder(task_id,revision,job_id,actor_id,
            create_uid,write_uid,create_date,write_date) VALUES(%s,%s,%s,%s,%s,%s,timezone('UTC',now()),timezone('UTC',now()))
            ON CONFLICT(task_id,revision) DO NOTHING""",[self.id,revision,ident,self.env.uid,self.env.uid,self.env.uid])
        self.env.cr.execute('SELECT job_id FROM mp_aurora_reminder WHERE task_id=%s AND revision=%s',[self.id,revision])
        if self.env.cr.fetchone()!=(ident,):raise ValidationError(_('Reminder occurrence changed.'))

    def _mp_reminder_resource(self):
        self.ensure_one();self.check_access('write')
        self.env.cr.execute('SELECT list_id FROM mp_aurora_task WHERE id=%s FOR SHARE',[self.id])
        row=self.env.cr.fetchone()
        if not row:raise AccessError(_('Task unavailable.'))
        self.env.cr.execute('SELECT id FROM mp_aurora_task_list WHERE id=%s FOR SHARE',[row[0]])
        self.check_access('write')
        return self

    def _deliver_reminder(self,revision):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM mp_aurora_task WHERE id=%s FOR UPDATE',[self.id])
        self.invalidate_recordset();facts=self._facts()
        current,option,due,recipient,active,list_active,done,user_active,share=facts
        if current!=revision or option=='none' or not due or not recipient or not active or not list_active or done or not user_active or share:
            return dict(outcome='obsolete')
        self.env.cr.execute('SELECT id FROM res_users WHERE id=%s AND active AND NOT share FOR SHARE',[recipient])
        if not self.env.cr.fetchone():return dict(outcome='obsolete')
        self.with_user(recipient).check_access('read')
        self.env.cr.execute("""INSERT INTO mp_aurora_notification(task_id,revision,recipient_id,title,due_date,is_read,
            create_uid,write_uid,create_date,write_date) VALUES(%s,%s,%s,%s,%s,false,%s,%s,timezone('UTC',now()),timezone('UTC',now()))
            ON CONFLICT(task_id,revision) DO NOTHING""",[self.id,revision,recipient,self.name,due,self.env.uid,self.env.uid])
        return dict(outcome='notified')

    @api.depends('due_date','reminder')
    def _compute_reminder_at(self):
        for row in self:row.reminder_at=row.due_date-timedelta(minutes=int(row.reminder)) if row.due_date and row.reminder in ('0','15','60','1440') else False

    @api.depends('stage_id')
    def _compute_completed(self):
        for row in self:
            origin=row._origin
            if type(origin.id) is not int:row.completed=False;continue
            origin.check_access('read')
            self.env.cr.execute('SELECT COALESCE(s.done,false) FROM mp_aurora_task t LEFT JOIN mp_aurora_task_stage s ON s.id=t.stage_id WHERE t.id=%s',[origin.id])
            result=self.env.cr.fetchone();row.completed=result[0] if result else False

    def _compute_reminder_status(self):
        now=fields.Datetime.now()
        for row in self:
            if type(row._origin.id) is not int:row.reminder_status='disabled';continue
            row._origin.check_access('read')
            facts=row._origin._facts()
            if not facts:row.reminder_status='cancelled';continue
            revision,option,due,recipient,active,list_active,done,user_active,share=facts
            if option=='none':row.reminder_status='disabled';continue
            self.env.cr.execute("""SELECT n.id,COALESCE(j.state,h.terminal_state),j.deadline_at,j.error_code
                FROM mp_aurora_reminder o LEFT JOIN mp_job j ON j.public_id=o.job_id
                LEFT JOIN mp_job_identity h ON h.job_public_id=o.job_id
                LEFT JOIN mp_aurora_notification n ON n.task_id=o.task_id AND n.revision=o.revision
                WHERE o.task_id=%s AND o.revision=%s""",[row._origin.id,revision])
            state=self.env.cr.fetchone()
            if state and state[0]:row.reminder_status='sent'
            elif not active or not list_active or done or not due or not recipient:row.reminder_status='cancelled'
            elif due-timedelta(minutes=int(option))+timedelta(days=1)<=now:row.reminder_status='expired'
            elif state and state[1] in ('pending','retry','running','held'):row.reminder_status='queued'
            elif state and state[1]=='cancelled':row.reminder_status='cancelled'
            else:row.reminder_status='blocked'

    def _set_completion(self,done):
        self.check_access('write')
        for row in self:
            self.env.cr.execute('SELECT id FROM mp_aurora_task_stage WHERE list_id=%s AND done=%s ORDER BY sequence,id LIMIT 1',[row.list_id.id,done])
            stage=self.env.cr.fetchone()
            if done and not stage:raise ValidationError(_('The list owner must add a completed stage.'))
            row.write({'stage_id':stage[0] if stage else False})
        return True

    def action_complete(self):return self._set_completion(True)
    def action_reopen(self):return self._set_completion(False)

    @api.constrains("list_id", "stage_id")
    def _check_stage_list(self):
        for task in self:
            if not task.stage_id:continue
            # The current task authorizes this relationship, including an
            # assignee who cannot browse/configure the containing list/stage.
            # Touch the stage tuple so concurrent referenced-stage edits retry
            # under the native repeatable-read transaction before checking use.
            self.env.cr.execute('UPDATE mp_aurora_task_stage SET write_date=write_date WHERE id=%s AND list_id=%s RETURNING id',[task.stage_id.id,task.list_id.id])
            if not self.env.cr.fetchone():raise ValidationError(_("Select a stage from the task's list."))

    @api.constrains("assignee_id")
    def _check_internal_assignee(self):
        if any(assignee.share or not assignee.active for assignee in self.assignee_id):
            raise ValidationError(_("The assignee must be an active internal user."))
