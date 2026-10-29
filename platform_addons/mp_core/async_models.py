"""Site-owned scheduler control metadata; no public ORM CRUD authority.

Workspace/actor tags route private dispatch, not a permission grant. Public
projections must authorize their current actor/scope separately. Native Odoo
owns these tables; the private scheduler adapter uses bounded SQL operations.
"""
from odoo import fields, models


class DispatchControl(models.Model):
    _name = 'mp.dispatch.control'
    _description = 'Private site dispatch generation'
    _log_access = False

    site_id = fields.Char(required=True, index=True)
    release_digest = fields.Char(required=True)
    state = fields.Selection([('paused', 'Paused'), ('enabled', 'Enabled'), ('restoring', 'Restoring')], required=True, default='paused')
    generation = fields.Integer(required=True, default=1)
    _site_unique = models.Constraint('UNIQUE(site_id)', 'One dispatch control per site')
    _generation_positive = models.Constraint('CHECK(generation > 0)', 'Dispatch generation must be positive')


class Job(models.Model):
    _name = 'mp.job'
    _description = 'Private durable platform job'
    _log_access = False

    public_id = fields.Char(required=True, index=True)
    site_id = fields.Char(required=True, index=True)
    workspace_id = fields.Many2one('mp.workspace', required=True, ondelete='restrict', index=True)
    actor_id = fields.Many2one('mp.principal', required=True, ondelete='restrict', index=True)
    installation_id = fields.Many2one('mp.plugin.installation', required=True, ondelete='restrict', index=True)
    handler = fields.Char(required=True, index=True)
    handler_version = fields.Integer(required=True, default=1)
    release_digest = fields.Char(required=True, index=True)
    payload = fields.Json(required=True)
    input_digest = fields.Char(required=True)
    idempotency_key = fields.Char(required=True)
    effect_mode = fields.Selection([('idempotent', 'Idempotent'), ('reconcile', 'Reconcile uncertain effects')], required=True)
    state = fields.Selection([(v, v.replace('_', ' ').title()) for v in ['pending', 'running', 'retry', 'completed', 'dead_letter', 'cancelled', 'outcome_unknown', 'held']], required=True, default='pending', index=True)
    attempts = fields.Integer(required=True, default=0)
    max_attempts = fields.Integer(required=True, default=5)
    claim_generation = fields.Integer(required=True, default=0)
    dispatch_generation = fields.Integer(required=True)
    lease_owner = fields.Char()
    lease_until = fields.Datetime(index=True)
    available_at = fields.Datetime(required=True, index=True)
    deadline_at = fields.Datetime(required=True)
    cancel_requested = fields.Boolean(required=True, default=False)
    effect_started = fields.Boolean(required=True, default=False)
    progress = fields.Integer(required=True, default=0)
    result = fields.Json()
    error_code = fields.Char()
    created_at = fields.Datetime(required=True)
    finished_at = fields.Datetime()
    _public_unique = models.Constraint('UNIQUE(public_id)', 'Job ID must be unique')
    _dedup_unique = models.Constraint('UNIQUE(site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)', 'Job deduplication scope must be unique')
    _bounds = models.Constraint('CHECK(attempts >= 0 AND max_attempts BETWEEN 1 AND 16 AND claim_generation >= 0 AND handler_version > 0 AND dispatch_generation > 0 AND progress BETWEEN 0 AND 100)', 'Invalid scheduler bounds')


class Outbox(models.Model):
    _name = 'mp.outbox'
    _description = 'Private transactional domain outbox'
    _log_access = False

    public_id = fields.Char(required=True, index=True)
    site_id = fields.Char(required=True, index=True)
    workspace_id = fields.Many2one('mp.workspace', required=True, ondelete='restrict', index=True)
    actor_id = fields.Many2one('mp.principal', required=True, ondelete='restrict')
    installation_id = fields.Many2one('mp.plugin.installation', required=True, ondelete='restrict')
    plugin_id = fields.Char(required=True)
    topic = fields.Char(required=True, index=True)
    schema_version = fields.Integer(required=True)
    aggregate_id = fields.Char(required=True, index=True)
    aggregate_sequence = fields.Integer()
    occurred_at = fields.Datetime(required=True)
    correlation_id = fields.Char(required=True)
    causation_id = fields.Char()
    payload = fields.Json(required=True)
    release_digest = fields.Char(required=True)
    dispatch_generation = fields.Integer(required=True)
    state = fields.Selection([('pending', 'Pending'), ('published', 'Published'), ('held', 'Held')], required=True, default='pending', index=True)
    _public_unique = models.Constraint('UNIQUE(public_id)', 'Event ID must be unique')
    _positive_version = models.Constraint('CHECK(schema_version > 0 AND dispatch_generation > 0 AND (aggregate_sequence IS NULL OR aggregate_sequence > 0))', 'Invalid event version or sequence')
