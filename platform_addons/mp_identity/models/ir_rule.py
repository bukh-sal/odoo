from odoo import api, models

from ..scopes import current_scope


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def _eval_context(self):
        context = super()._eval_context()
        scope = current_scope(self.env, required=False)
        context["mp_workspace_id"] = scope.workspace_id if scope else 0
        return context

    def _compute_domain_keys(self):
        return super()._compute_domain_keys() + ["mp_workspace_id", "mp_policy_generation"]

    def _compute_domain_context_values(self):
        scope = current_scope(self.env, required=False)
        for key in self._compute_domain_keys():
            if key == "mp_workspace_id":
                yield scope.workspace_id if scope else 0
            elif key == "mp_policy_generation":
                yield scope.policy_generation if scope else 0
            else:
                value = self.env.context.get(key)
                yield tuple(value) if isinstance(value, list) else value
