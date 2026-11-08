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
    workspace_id = fields.Many2one('mp.workspace', required=False, ondelete='restrict', index=True)
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
    _dedup_unique = models.Constraint('UNIQUE NULLS NOT DISTINCT(site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)', 'Job deduplication scope must be unique')
    _bounds = models.Constraint('CHECK(attempts >= 0 AND max_attempts BETWEEN 1 AND 16 AND claim_generation >= 0 AND handler_version > 0 AND dispatch_generation > 0 AND progress BETWEEN 0 AND 100)', 'Invalid scheduler bounds')
    _history_order = models.Index('(site_id, workspace_id, actor_id, (COALESCE(finished_at, created_at)) DESC, public_id)')


class JobIdentity(models.Model):
    _name = 'mp.job.identity'
    _description = 'Private job identity and compact terminal history'
    _log_access = False

    site_id = fields.Char(required=True)
    workspace_id = fields.Integer(required=False)
    actor_id = fields.Integer(required=True)
    installation_id = fields.Integer(required=True)
    handler = fields.Char(required=True)
    handler_version = fields.Integer(required=True)
    idempotency_key = fields.Char(required=True)
    # Live reservations carry no copy of the job. Terminal metadata is
    # populated only by the transaction that removes the live row.
    job_public_id = fields.Char()
    input_digest = fields.Char()
    release_digest = fields.Char()
    effect_mode = fields.Char()
    terminal_state = fields.Char()
    finished_at = fields.Datetime()
    archived_at = fields.Datetime()
    _scope_key = models.Constraint(
        'UNIQUE NULLS NOT DISTINCT(site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)',
        'Job identity must be unique within its scope',
    )
    _original_job = models.Constraint('UNIQUE(job_public_id)', 'Archived job ID must be unique')
    _history_order = models.Index('(site_id, workspace_id, actor_id, finished_at DESC, job_public_id) WHERE job_public_id IS NOT NULL')
    _terminal_record = models.Constraint(
        """CHECK (
            (job_public_id IS NULL AND input_digest IS NULL AND release_digest IS NULL
             AND effect_mode IS NULL AND terminal_state IS NULL AND finished_at IS NULL AND archived_at IS NULL)
            OR
            (job_public_id IS NOT NULL AND input_digest IS NOT NULL AND release_digest IS NOT NULL
             AND effect_mode IS NOT NULL AND effect_mode = 'idempotent'
             AND terminal_state IS NOT NULL AND terminal_state IN ('completed','dead_letter','cancelled')
             AND finished_at IS NOT NULL AND archived_at IS NOT NULL)
        )""",
        'Job history must be empty or a complete terminal record',
    )


class JobSchedule(models.Model):
    _name = 'mp.job.schedule'
    _description = 'Private versioned recurring job schedule'
    _log_access = False

    public_id = fields.Char(required=True, index=True)
    site_id = fields.Char(required=True, index=True)
    workspace_id = fields.Many2one('mp.workspace', required=True, ondelete='restrict')
    actor_id = fields.Many2one('mp.principal', required=True, ondelete='restrict')
    installation_id = fields.Many2one('mp.plugin.installation', required=True, ondelete='restrict')
    idempotency_key = fields.Char(required=True)
    release_digest = fields.Char(required=True)
    handler = fields.Char(required=True)
    handler_version = fields.Integer(required=True)
    config_version = fields.Integer(required=True, default=1)
    rule = fields.Json(required=True)
    payload = fields.Json(required=True)
    input_digest = fields.Char(required=True)
    creation_digest = fields.Char(required=True)
    state = fields.Selection([(state,state.title()) for state in ('active','paused','held')], required=True)
    next_at = fields.Datetime(required=True)
    considered_at = fields.Datetime()
    # Public job IDs survive archival; an FK to the live queue would not.
    outstanding_job_id = fields.Char()
    last_tick_at = fields.Datetime()
    last_tick = fields.Json()
    created_at = fields.Datetime(required=True)
    error_code = fields.Char()
    _public_unique = models.Constraint('UNIQUE(public_id)', 'Schedule identity must be unique')
    _scope_key = models.Constraint('UNIQUE(site_id,workspace_id,actor_id,installation_id,idempotency_key)', 'Schedule creation identity must be unique')
    _versions = models.Constraint('CHECK(handler_version > 0 AND config_version > 0)', 'Positive schedule versions required')
    _due = models.Index("(site_id,release_digest,next_at,last_tick_at,public_id) WHERE state='active'")


class JobOccurrence(models.Model):
    _name = 'mp.job.occurrence'
    _description = 'Private immutable recurring occurrence receipt'
    _log_access = False

    site_id = fields.Char(required=True)
    schedule_id = fields.Char(required=True)
    nominal_at = fields.Datetime(required=True)
    job_public_id = fields.Char(required=True)
    config_version = fields.Integer(required=True)
    input_digest = fields.Char(required=True)
    release_digest = fields.Char(required=True)
    created_at = fields.Datetime(required=True)
    _nominal_unique = models.Constraint('UNIQUE(site_id,schedule_id,nominal_at)', 'Occurrence identity must survive edits and rotation')
    _job_unique = models.Constraint('UNIQUE(job_public_id)', 'One receipt per recurring job')
    _version = models.Constraint('CHECK(config_version > 0)', 'Positive occurrence version required')


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
