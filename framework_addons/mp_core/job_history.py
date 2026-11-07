"""Read-only native projection of an actor's own job receipts."""

from odoo import fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_identity.scopes import current_scope


class JobHistory(models.Model):
    _name = 'mp.job.history'
    _description = 'My background jobs'
    _inherit = 'mp.workspace.scoped'
    _auto = False
    _log_access = False
    _rec_name = 'public_id'
    _order = 'status_at desc, public_id'

    public_id = fields.Char(string='Job ID', readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'), ('running', 'Running'), ('retry', 'Retry'),
        ('completed', 'Completed'), ('dead_letter', 'Failed'), ('cancelled', 'Cancelled'),
        ('outcome_unknown', 'Outcome unknown'), ('held', 'Held'),
    ], readonly=True)
    status_at = fields.Datetime(string='Submitted or finished', readonly=True)
    archived = fields.Boolean(readonly=True)

    def _history_scope(self, *, required=True):
        scope = current_scope(self.env, required=required)
        if scope and scope.principal_kind != 'human':
            raise AccessError('Background job history requires a human workspace member')
        return scope

    def _history_query(self, scope):
        # Each branch is constrained before filtering, counting or paging by
        # the ORM. Expose only receipt metadata, never the underlying record.
        binding = (current_release(self.env)['site_id'], scope.workspace_id, scope.principal_id) if scope else ('', 0, 0)
        return SQL("""
            SELECT 2::bigint*id AS id, workspace_id, public_id, state,
                   COALESCE(finished_at,created_at) AS status_at, false AS archived
              FROM mp_job WHERE site_id=%s AND workspace_id=%s AND actor_id=%s
            UNION ALL
            SELECT 2::bigint*id+1 AS id, workspace_id, job_public_id, terminal_state,
                   finished_at, true AS archived
              FROM mp_job_identity WHERE site_id=%s AND workspace_id=%s AND actor_id=%s
                AND job_public_id IS NOT NULL
        """, *binding, *binding)

    @property
    def _table_query(self):
        return self._history_query(self._history_scope(required=False))

    def _mp_guard(self, operation):
        if operation != 'read':
            raise AccessError('Background job history is read-only')
        scope = self._history_scope()
        ids = {ident for ident in self._origin.ids if isinstance(ident, int)}
        if ids:
            binding = (current_release(self.env)['site_id'], scope.workspace_id, scope.principal_id)
            # Projected IDs encode the source table and its primary key.
            # Check those keys directly before the native read window starts.
            self.env.cr.execute("""SELECT 2::bigint*id FROM mp_job
                WHERE id=ANY(%s) AND site_id=%s AND workspace_id=%s AND actor_id=%s
                UNION ALL SELECT 2::bigint*id+1 FROM mp_job_identity
                WHERE id=ANY(%s) AND site_id=%s AND workspace_id=%s AND actor_id=%s AND job_public_id IS NOT NULL""",
                [[ident//2 for ident in ids if ident%2==0], *binding,
                 [(ident-1)//2 for ident in ids if ident%2], *binding])
            if {row[0] for row in self.env.cr.fetchall()} != ids:
                raise AccessError('Job receipt unavailable in current workspace')
        return scope
