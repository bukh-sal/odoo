"""Minimal core registry metadata. Mutations are operator-managed until G5."""
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.mp_identity.scopes import current_scope, canonical_uuid


class ApiHttpErrors(models.AbstractModel):
    _inherit='ir.http'

    @classmethod
    def _handle_error(cls,exception):
        from werkzeug.exceptions import RequestEntityTooLarge
        from odoo.http import request
        if isinstance(exception,RequestEntityTooLarge) and request.httprequest.path.startswith('/api/v1/'):
            from .controllers import audit
            ident=str(uuid4());request.env.cr.rollback();audit('denied',ident)
            return request.make_json_response({'error':{'code':'VALIDATION_FAILED','message':'Request exceeds payload limit','request_id':ident,'retryable':False,'details':{}}},status=400)
        response=super()._handle_error(exception)
        if getattr(request.dispatcher,'routing_type',None)=='jsonrpc':
            # Preserve the private native error class/JSON-RPC ID expected by
            # widgets; remove upstream debug/arguments/context and dynamic text.
            # The generic SDK never exposes this transport at all.
            try:payload=response.get_json()
            except (ValueError,AttributeError):return response
            if isinstance(payload,dict) and isinstance(payload.get('error'),dict):
                import json
                ident=str(uuid4());data=payload['error'].get('data') or {}
                payload['error']['message']='Operation denied or invalid'
                payload['error']['data']={'name':data.get('name','odoo.exceptions.UserError'),'message':'Operation denied or invalid. Reference '+ident,'request_id':ident}
                response.set_data(json.dumps(payload))
        return response


class Workspace(models.Model):
    _inherit = 'mp.workspace'
    slug = fields.Char(default=lambda self:str(uuid4()),required=True,index=True)
    default_locale = fields.Char(default='en-US',required=True)
    timezone = fields.Char(default='UTC',required=True)
    _slug_unique = models.Constraint('UNIQUE(slug)','Workspace slug must be unique')

    def write(self,values):
        if 'public_id' in values:raise AccessError('Workspace identity is immutable')
        result=super().write(values)
        if {'state','name','default_locale','timezone'} & values.keys():self._bump_policy()
        return result


class Principal(models.Model):
    _inherit = 'mp.principal'

    def write(self,values):
        if {'public_id','kind','user_id'} & values.keys():raise AccessError('Principal identity/mapping is immutable; provision a new principal')
        return super().write(values)


class WorkspacePlugin(models.Model):
    _inherit = 'mp.workspace.plugin'
    installation_id = fields.Many2one('mp.plugin.installation',required=True,ondelete='restrict',index=True)

    @api.constrains('plugin_id','installation_id')
    def _installation_identity(self):
        if any(row.plugin_id!=row.installation_id.plugin_id for row in self):raise ValidationError('Feature installation mismatch')


class Installation(models.Model):
    _name = 'mp.plugin.installation'
    _description = 'Site plugin installation'
    public_id = fields.Char(default=lambda self:str(uuid4()), required=True, index=True, readonly=True)
    plugin_id = fields.Char(required=True, index=True)
    version = fields.Char(required=True)
    artifact_digest = fields.Char(required=True)
    runtime = fields.Selection([('native','Native'),('external_service','External service')],required=True)
    state = fields.Selection([('installed','Installed'),('suspended','Suspended'),('removed','Removed')],required=True,default='installed')
    manifest = fields.Json(required=True)
    _plugin_unique = models.Constraint('UNIQUE(plugin_id)', 'One plugin installation per site')
    _public_unique = models.Constraint('UNIQUE(public_id)', 'Installation ID must be unique')

    @api.constrains('manifest','plugin_id','version','public_id','runtime')
    def _validate_metadata(self):
        from modular_platform.contracts import normalize_manifest
        for record in self:
            canonical_uuid(record.public_id)
            manifest = normalize_manifest(record.manifest, core=record.plugin_id.startswith('org.modularplatform.'))
            if manifest['plugin']['id'] != record.plugin_id or manifest['plugin']['version'] != record.version or manifest['runtime']['kind'] != record.runtime:
                raise ValidationError('Installation identity mismatch')

    def write(self, values):
        if {'plugin_id','public_id','runtime'} & values.keys(): raise AccessError('Installation identity is immutable')
        if 'artifact_digest' in values:
            for record in self:
                if values['artifact_digest']!=record.artifact_digest and values.get('version',record.version)==record.version:
                    raise ValidationError('A different artifact requires a different package version')
        result=super().write(values)
        if {'state','version','manifest'} & values.keys():
            self.env['mp.workspace.plugin'].search([('installation_id','in',self.ids)]).workspace_id._bump_policy()
        return result


class Binding(models.Model):
    _name = 'mp.service.binding'
    _description = 'Locked service binding'
    public_id = fields.Char(required=True, index=True)
    workspace_id = fields.Many2one('mp.workspace',required=True,ondelete='restrict',index=True)
    consumer_id = fields.Many2one('mp.plugin.installation',required=True,ondelete='restrict')
    alias = fields.Char(required=True)
    descriptor = fields.Json(required=True)
    state = fields.Selection([('active','Active'),('unavailable','Unavailable')],default='active',required=True)
    _binding_unique = models.Constraint('UNIQUE(public_id)', 'Binding ID must be unique')
    _alias_unique = models.Constraint('UNIQUE(workspace_id,consumer_id,alias)', 'Alias must be unique for consumer/workspace')

    @api.model_create_multi
    def create(self,values_list):
        rows=super().create(values_list);rows.workspace_id._bump_policy();return rows

    @api.constrains('descriptor','public_id','workspace_id','consumer_id','alias')
    def _validate_descriptor(self):
        from modular_platform.contracts import validate
        for row in self:
            validate('binding',row.descriptor)
            if (row.public_id,row.workspace_id.public_id,row.consumer_id.public_id,row.alias) != tuple(row.descriptor[k] for k in ['binding_id','workspace_id','consumer_installation_id','alias']):
                raise ValidationError('Binding identity mismatch')

    def write(self,values):
        if {'public_id','workspace_id','consumer_id','alias'} & values.keys():raise AccessError('Binding identity is immutable')
        result=super().write(values);self.workspace_id._bump_policy();return result


class Grant(models.Model):
    _name = 'mp.plugin.grant'
    _description = 'Approved integration capability'
    installation_id = fields.Many2one('mp.plugin.installation',required=True,ondelete='cascade',index=True)
    workspace_id = fields.Many2one('mp.workspace',required=True,ondelete='cascade',index=True)
    capability = fields.Char(required=True,index=True)
    state = fields.Selection([('approved','Approved'),('revoked','Revoked')],required=True,default='approved')
    policy_version = fields.Integer(required=True,default=1)
    _grant_unique = models.Constraint('UNIQUE(installation_id,workspace_id,capability)', 'Capability grant must be unique')

    @api.model_create_multi
    def create(self,values_list):
        rows=super().create(values_list);rows.workspace_id._bump_policy();return rows

    def write(self,values):
        result=super().write(values);self.workspace_id._bump_policy();return result


class Audit(models.Model):
    _name = 'mp.audit.event'
    _description = 'Redacted platform audit'
    _order = 'id desc'
    actor_id = fields.Char(index=True)
    workspace_public_id = fields.Char(index=True)
    plugin_id = fields.Char(index=True)
    action = fields.Char(required=True)
    target_id = fields.Char()
    decision = fields.Selection([('allowed','Allowed'),('denied','Denied')],required=True)
    request_id = fields.Char(required=True,index=True)
    metadata = fields.Json(default=dict)


class ServiceOutcome(models.Model):
    _name = 'mp.service.outcome'
    _description = 'Scoped same-database operation result'
    actor_id = fields.Char(required=True)
    site_id = fields.Char(required=True)
    workspace_id = fields.Many2one('mp.workspace',required=True,ondelete='restrict')
    service_id = fields.Char(required=True)
    contract_major = fields.Integer(required=True)
    provider_id = fields.Char(required=True)
    method = fields.Char(required=True)
    key = fields.Char(required=True)
    input_digest = fields.Char(required=True)
    binding_id = fields.Char(required=True)
    binding_generation = fields.Integer(required=True)
    api_version = fields.Char(required=True)
    state = fields.Selection([('in_progress','In progress'),('completed','Completed'),('outcome_unknown','Outcome unknown')],required=True)
    result = fields.Json()
    expires_at = fields.Datetime(required=True)
    _scope_unique = models.Constraint('UNIQUE(actor_id,site_id,workspace_id,service_id,contract_major,provider_id,method,key)', 'Idempotency scope/key must be unique')


class SupportedInstallationGuard(models.AbstractModel):
    _inherit = 'mp.workspace.scoped'

    def _mp_guard(self, operation):
        scope = super()._mp_guard(operation)
        self.env['mp.plugin.installation'].flush_model(['state'])
        # Current metadata only, after actor/scope authorization. No business
        # access elevation or administrator fallback. Applies to native RPC too.
        self.env.cr.execute("SELECT state FROM mp_plugin_installation WHERE plugin_id=%s",[self._mp_plugin_id])
        row = self.env.cr.fetchone()
        if not row or row[0] != 'installed': raise AccessError('Plugin installation unavailable')
        return scope
