from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Principal(models.Model):
    _name = "mp.principal"
    _description = "Platform principal"

    name = fields.Char(required=True)
    public_id = fields.Char(required=True, default=lambda self: str(uuid4()), index=True, readonly=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict", index=True)
    kind = fields.Selection([("human", "Human"), ("service", "Service")], required=True, default="human")
    state = fields.Selection([("active", "Active"), ("suspended", "Suspended")], required=True, default="active")
    _public_id_unique = models.Constraint("UNIQUE(public_id)", "Principal ID must be unique")
    _user_unique = models.Constraint("UNIQUE(user_id)", "A user maps to one principal")

    @api.constrains("kind", "user_id")
    def _restricted_service_identity(self):
        for principal in self:
            if principal.kind == "service" and (principal.user_id._is_admin() or principal.user_id.has_group("base.group_system")):
                raise ValidationError("A technical identity cannot use an administrator backing user")


class Workspace(models.Model):
    _name = "mp.workspace"
    _description = "Platform workspace"

    name = fields.Char(required=True)
    public_id = fields.Char(required=True, default=lambda self: str(uuid4()), index=True, readonly=True)
    state = fields.Selection([("active", "Active"), ("suspended", "Suspended")], required=True, default="active")
    policy_generation = fields.Integer(default=1, required=True, readonly=True)
    membership_ids = fields.One2many("mp.membership", "workspace_id")
    _public_id_unique = models.Constraint("UNIQUE(public_id)", "Workspace ID must be unique")

    def _bump_policy(self):
        # Private metadata update after the caller's ORM mutation was authorized.
        if self.ids:
            self.env.cr.execute("UPDATE mp_workspace SET policy_generation = policy_generation + 1 WHERE id = ANY(%s)", [self.ids])
            self.invalidate_recordset(["policy_generation"])


class Membership(models.Model):
    _name = "mp.membership"
    _description = "Workspace membership"

    principal_id = fields.Many2one("mp.principal", required=True, ondelete="cascade", index=True)
    workspace_id = fields.Many2one("mp.workspace", required=True, ondelete="cascade", index=True)
    role = fields.Selection([("viewer", "Viewer"), ("editor", "Editor"), ("administrator", "Administrator")], required=True)
    state = fields.Selection([("active", "Active"), ("revoked", "Revoked")], required=True, default="active")
    _membership_unique = models.Constraint("UNIQUE(principal_id,workspace_id)", "Membership must be unique")

    @api.model_create_multi
    def create(self, values):
        records = super().create(values)
        records.workspace_id._bump_policy()
        return records

    def write(self, values):
        previous = self.workspace_id
        result = super().write(values)
        (previous | self.workspace_id)._bump_policy()
        return result

    def unlink(self):
        workspaces = self.workspace_id
        result = super().unlink()
        workspaces._bump_policy()
        return result


class WorkspacePlugin(models.Model):
    _name = "mp.workspace.plugin"
    _description = "Workspace feature policy (G1 skeleton)"

    workspace_id = fields.Many2one("mp.workspace", required=True, ondelete="cascade", index=True)
    plugin_id = fields.Char(required=True, index=True)
    availability = fields.Selection([("enabled", "Enabled"), ("suspended", "Suspended")], default="enabled", required=True)
    _feature_unique = models.Constraint("UNIQUE(workspace_id,plugin_id)", "Workspace feature must be unique")

    @api.model_create_multi
    def create(self, values):
        records = super().create(values)
        records.workspace_id._bump_policy()
        return records

    def write(self, values):
        result = super().write(values)
        self.workspace_id._bump_policy()
        return result


class ServiceCredential(models.Model):
    _name = "mp.service.credential"
    _description = "Short-lived G1 technical credential"

    name = fields.Char(required=True)
    principal_id = fields.Many2one("mp.principal", required=True, ondelete="cascade")
    workspace_id = fields.Many2one("mp.workspace", required=True, ondelete="cascade")
    token_digest = fields.Char(required=True, index=True, groups="base.group_system")
    installation_public_id = fields.Char(required=True)
    audience = fields.Char(required=True, default="mp-host-v1")
    actions = fields.Char(required=True, default="read")
    expires_at = fields.Datetime(required=True)
    state = fields.Selection([("active", "Active"), ("revoked", "Revoked")], default="active", required=True)
    _token_unique = models.Constraint("UNIQUE(token_digest)", "Technical credential must be unique")

    @api.constrains("principal_id", "actions")
    def _validate_identity_and_actions(self):
        for credential in self:
            if credential.principal_id.kind != "service" or not set(credential.actions.split(",")) <= {"read", "create", "write", "unlink"}:
                raise ValidationError("Invalid technical identity or action scope")
