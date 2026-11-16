"""Framework authority metadata. Only private trusted-native helpers mutate it."""
from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResourcePolicy(models.Model):
    _name = 'mp.resource.policy'
    _description = 'Current authority for one application resource'

    public_id = fields.Char(required=True, index=True, readonly=True)
    installation_id = fields.Many2one('mp.plugin.installation', required=True, ondelete='restrict', index=True)
    workspace_id = fields.Many2one('mp.workspace', required=True, ondelete='restrict', index=True)
    model_name = fields.Char(required=True, index=True)
    resource_id = fields.Char(required=True, index=True)
    owner_id = fields.Many2one('mp.principal', required=True, ondelete='restrict', index=True)
    state = fields.Selection([('active', 'Active'), ('revoked', 'Revoked')], required=True)
    revision = fields.Integer(required=True, default=1)
    member_capabilities = fields.Json(required=True, default=list)
    _public_unique = models.Constraint('UNIQUE(public_id)', 'Resource policy identity must be unique')
    _resource_unique = models.Constraint('UNIQUE(installation_id,workspace_id,model_name,resource_id)', 'One policy per resource')
    _revision_positive = models.Constraint('CHECK(revision > 0)', 'Policy revision must be positive')

    def _check_access(self, operation):
        raise AccessError('Resource authority is available only through private application helpers')

    @api.model
    def _has_field_access(self, field, operation):
        # The native descriptor checks this before its field-cache lookup.
        # Helpers use constrained SQL, not a privileged ORM recordset.
        return False

    @api.model_create_multi
    def create(self, values_list):
        raise AccessError('Resource authority is not native-RPC writable')

    def write(self, values):
        raise AccessError('Resource authority is not native-RPC writable')

    def unlink(self):
        raise AccessError('Resource authority tombstones must be retained')


class ResourceGrant(models.Model):
    _name = 'mp.resource.grant'
    _description = 'Current principal capability for an application resource'

    policy_id = fields.Many2one('mp.resource.policy', required=True, ondelete='restrict', index=True)
    principal_id = fields.Many2one('mp.principal', required=True, ondelete='restrict', index=True)
    capability = fields.Char(required=True, index=True)
    state = fields.Selection([('approved', 'Approved'), ('revoked', 'Revoked')], required=True)
    _grant_unique = models.Constraint('UNIQUE(policy_id,principal_id,capability)', 'Resource capability must be unique')

    def _check_access(self, operation):
        raise AccessError('Resource authority is available only through private application helpers')

    @api.model
    def _has_field_access(self, field, operation):
        return False

    @api.model_create_multi
    def create(self, values_list):
        raise AccessError('Resource authority is not native-RPC writable')

    def write(self, values):
        raise AccessError('Resource authority is not native-RPC writable')

    def unlink(self):
        raise AccessError('Resource authority tombstones must be retained')
