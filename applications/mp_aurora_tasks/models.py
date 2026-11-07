from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class AuroraTaskList(models.Model):
    _name = "mp.aurora.task.list"
    _description = "Aurora task list"

    name = fields.Char(required=True)
    description = fields.Text()
    owner_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    member_ids = fields.Many2many("res.users", string="Members", domain=[("share", "=", False)])
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, values_list):
        return super().create([{**values, "owner_id": self.env.uid} for values in values_list])

    def write(self, values):
        if "owner_id" in values:
            raise AccessError(_("The owner is set when the list is created."))
        if {"active", "member_ids"} & values.keys() and any(
            record.owner_id != self.env.user for record in self
        ):
            raise AccessError(_("Only the list owner can manage membership or archive the list."))
        return super().write(values)

    @api.constrains("member_ids")
    def _check_internal_members(self):
        if any(member.share for member in self.member_ids):
            raise ValidationError(_("List members must be internal users."))


class AuroraTaskStage(models.Model):
    _name = "mp.aurora.task.stage"
    _description = "Aurora task stage"
    _order = "sequence, id"

    name = fields.Char(required=True)
    list_id = fields.Many2one("mp.aurora.task.list", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    done = fields.Boolean()

    def write(self, values):
        if "list_id" in values and any(stage.list_id.id != values["list_id"] for stage in self):
            raise ValidationError(_("Create a stage in the destination list."))
        return super().write(values)


class AuroraTask(models.Model):
    _name = "mp.aurora.task"
    _description = "Aurora task"

    name = fields.Char(required=True)
    description = fields.Text()
    list_id = fields.Many2one("mp.aurora.task.list", required=True, ondelete="cascade", index=True)
    stage_id = fields.Many2one("mp.aurora.task.stage", ondelete="set null",
                               domain="[('list_id', '=', list_id)]")
    creator_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    assignee_id = fields.Many2one("res.users", ondelete="set null", domain=[("share", "=", False)])
    due_date = fields.Datetime()
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, values_list):
        return super().create([
            {**values, "creator_id": self.env.uid, "active": True} for values in values_list
        ])

    def write(self, values):
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
        return super().write(values)

    @api.constrains("list_id", "stage_id")
    def _check_stage_list(self):
        if any(task.stage_id and task.stage_id.list_id != task.list_id for task in self):
            raise ValidationError(_("Select a stage from the task's list."))

    @api.constrains("assignee_id")
    def _check_internal_assignee(self):
        if any(assignee.share for assignee in self.assignee_id):
            raise ValidationError(_("The assignee must be an internal user."))
